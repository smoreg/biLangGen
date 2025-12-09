#!/usr/bin/env python3
"""Bilingual video generator CLI.

Usage:
    python main.py run -i txt_source/TEST.txt -s ru -t es
    python main.py list
    python main.py resume TEST_ru_es --open
"""

import argparse
import atexit
import platform
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from project import Project, ProjectManager, Pipeline, PipelineConfig
from utils.progress import create_progress_callback

# Global caffeinate process (macOS only)
_caffeinate_proc = None


def _start_caffeinate():
    """Start caffeinate on macOS to prevent sleep during long operations."""
    global _caffeinate_proc
    if platform.system() != "Darwin":
        return
    if _caffeinate_proc is not None:
        return  # Already running

    try:
        # -d: prevent display sleep
        # -i: prevent idle sleep
        # -m: prevent disk sleep
        _caffeinate_proc = subprocess.Popen(
            ["caffeinate", "-dim"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        atexit.register(_stop_caffeinate)
        # Handle SIGTERM and SIGINT (Ctrl+C) to cleanup caffeinate
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        print("☕ Caffeinate enabled (mac won't sleep)")
    except Exception:
        pass  # Silently ignore if caffeinate not available


def _signal_handler(signum, frame):
    """Handle signals to cleanup caffeinate before exit."""
    _stop_caffeinate()
    sys.exit(1)


def _stop_caffeinate():
    """Stop caffeinate process."""
    global _caffeinate_proc
    if _caffeinate_proc is not None:
        _caffeinate_proc.terminate()
        _caffeinate_proc = None


def cmd_run(args):
    """Create project from txt file and run full pipeline."""
    _start_caffeinate()

    # 1. Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # 2. Determine project name
    name = args.name or input_path.stem

    # 3. Create or load project
    pm = ProjectManager(Path("projects"))
    # Use tts_target_locale for project name if specified (e.g., es-latam vs es)
    target_for_slug = getattr(args, 'tts_target_locale', None) or args.target
    slug = f"{name}_{args.source}_{target_for_slug}"

    # Check if project already exists
    existing = pm.get_project(slug)
    if existing:
        if not args.force:
            print(f"Project already exists: {slug}")
            print("Use --force to regenerate or 'resume' to continue")
            sys.exit(1)
        # Force mode: reuse existing project (keeps audio cache)
        project = existing
        # Reset video step to force regeneration
        from project.manager import Progress, Status
        project.meta.progress["video"] = Progress(0, 0, Status.PENDING)
        project.meta.progress["audio_combined"] = Progress(0, 0, Status.PENDING)
        project.save_meta()
        print(f"Reusing project: {project.dir.name} (audio cache preserved, video will regenerate)")
    else:
        project = pm.create_project(name, args.source, args.target)
        print(f"Created project: {project.dir.name}")

    # 4. Load text
    text = input_path.read_text(encoding="utf-8")
    project.set_original_text(text)
    print(f"Loaded text: {len(text)} chars")

    # 5. Copy background image if provided
    if args.background:
        if args.background == "samename":
            # Find image with same name as input file
            bg_path = None
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                candidate = input_path.with_suffix(ext)
                if candidate.exists():
                    bg_path = candidate
                    break
            if bg_path is None:
                print(f"Warning: No background image found with same name as {input_path.stem}")
        else:
            bg_path = Path(args.background)
            if not bg_path.exists():
                print(f"Warning: Background image not found: {args.background}")
                bg_path = None

        if bg_path:
            import shutil
            dest = project.video_dir / f"background{bg_path.suffix}"
            shutil.copy(bg_path, dest)
            print(f"Background image: {dest}")

    # 6. Configure pipeline
    width, height = map(int, args.resolution.split("x"))
    if args.only_sentences:
        stop_after = "sentences"
    elif args.only_rare_words:
        stop_after = "rare_words_extract"
    elif args.stop_after_rare_words:
        stop_after = "rare_words_translate"
    else:
        stop_after = None
    # Validate wordcard options compatibility
    wordcard_mode = getattr(args, 'wordcard_mode', 'combined')
    tts_wc_source = getattr(args, 'tts_wordcards_source', None)
    tts_wc_target = getattr(args, 'tts_wordcards_target', None)
    tts_wc = getattr(args, 'tts_wordcards', None)

    if wordcard_mode == "combined" and (tts_wc_source or tts_wc_target):
        print("Error: --tts-wordcards-source and --tts-wordcards-target are only compatible with --wordcard-mode per_word")
        sys.exit(1)

    if wordcard_mode == "per_word" and tts_wc:
        print("Error: --tts-wordcards is only compatible with --wordcard-mode combined")
        print("       Use --tts-wordcards-source and --tts-wordcards-target for per_word mode")
        sys.exit(1)

    # Validate translate_context for OpenAI
    translate_context = getattr(args, 'translate_context', None)
    if args.translator == "openai" and not translate_context:
        print("Error: --translate-context is REQUIRED when using --translator openai")
        print("       Provide context about the text for better translation quality.")
        print("       Example: --translate-context 'Kurt Vonnegut Player Piano - dystopian satire'")
        sys.exit(1)

    config = PipelineConfig(
        source_lang=args.source,
        target_lang=args.target,
        tts_provider=args.tts,
        tts_provider_source=getattr(args, 'tts_source', None),
        tts_provider_target=getattr(args, 'tts_target', None),
        tts_provider_wordcards=tts_wc,
        tts_provider_wordcards_source=tts_wc_source,
        tts_provider_wordcards_target=tts_wc_target,
        translation_provider=args.translator,
        translation_parallel=args.translator_parallel,
        tts_parallel=args.tts_parallel,
        combine_workers=args.combine_workers,
        video_workers=args.video_workers,
        speed_source=args.speed_source,
        speed_target=args.speed_target,
        max_rare_words=args.rare_words,
        font_size=args.font_size,
        video_resolution=(width, height),
        tts_source_locale=args.tts_source_locale,
        tts_target_locale=args.tts_target_locale,
        stop_after=stop_after,
        enable_wordcard_audio=args.enable_wordcard_audio,
        wordcard_mode=wordcard_mode,
        max_sentence_length=1000000 if args.no_split_long else 95,
        translate_context=translate_context,
    )

    print(f"\nPipeline config:")
    tts_src = config.get_tts_provider_source()
    tts_tgt = config.get_tts_provider_target()
    tts_wc = config.get_tts_provider_wordcards()
    if tts_src == tts_tgt == tts_wc:
        print(f"  TTS: {tts_src} ({config.tts_parallel} threads)")
    else:
        print(f"  TTS: source={tts_src}, target={tts_tgt}, wordcards={tts_wc} ({config.tts_parallel} threads)")
    if config.tts_source_locale or config.tts_target_locale:
        src_loc = config.tts_source_locale or args.source
        tgt_loc = config.tts_target_locale or args.target
        print(f"  TTS locales: {src_loc} / {tgt_loc}")
    print(f"  Translator: {config.translation_provider} ({config.translation_parallel} threads)")
    print(f"  Languages: {args.source} -> {args.target}")
    print(f"  Resolution: {args.resolution}")

    # 7. Run pipeline
    print(f"\nRunning pipeline...")

    on_progress = create_progress_callback(print_every=10)
    pipeline = Pipeline(project, config)
    pipeline.run(on_progress)

    # 8. Done
    if args.only_sentences:
        sentences = project.get_sentences()
        print(f"\nSentences extracted: {len(sentences)}")
        print(f"Project saved to: {project.dir}")
    elif args.only_rare_words:
        sentences = project.get_sentences()
        rare_words = project.get_rare_words()
        print(f"\nSentences extracted: {len(sentences)}")
        print(f"Rare words extracted: {len(rare_words)}")
        print(f"Project saved to: {project.dir}")
    elif args.stop_after_rare_words:
        sentences = project.get_sentences()
        rare_words = project.get_rare_words()
        print(f"\nSentences: {len(sentences)}")
        print(f"Rare words: {len(rare_words)} (with translations)")
        print(f"Project saved to: {project.dir}")
        print("Stopped after rare_words_translate (before TTS/audio/video)")
    else:
        output = project.get_output_video_path()
        print(f"\nVideo generated: {output}")

        if args.open:
            import subprocess
            subprocess.run(["open", str(output)])


def cmd_list(args):
    """List all projects."""
    pm = ProjectManager(Path("projects"))
    projects = pm.list_projects()

    if not projects:
        print("No projects found")
        return

    print(f"Projects ({len(projects)}):\n")
    for name in sorted(projects):
        project = pm.get_project(name)

        # Calculate completion
        total_steps = len(project.meta.progress)
        complete_steps = sum(
            1 for p in project.meta.progress.values()
            if p.status.value == "complete"
        )

        status = "complete" if complete_steps == total_steps else f"{complete_steps}/{total_steps}"
        print(f"  {name} [{status}]")
        print(f"    {project.meta.source_lang} -> {project.meta.target_lang}")
        print(f"    Sentences: {project.meta.total_sentences}")
        print()


def cmd_quota(args):
    """Show quota usage for TTS and translation services."""
    from utils.quota_tracker import get_tracker

    tracker = get_tracker()
    print(tracker.format_report())


def cmd_dict(args):
    """Manage global word dictionary."""
    from analysis.word_dictionary import get_dictionary

    d = get_dictionary()

    if args.action == "stats":
        stats = d.stats()
        print(f"Word Dictionary Statistics:")
        print(f"  Total words: {stats['total_words']}")
        print(f"  With translations: {stats['translated']}")
        print(f"  Marked skip: {stats['skipped']}")
        print(f"  Projects: {stats['projects']}")
        print(f"\nLanguage pairs:")
        for pair, count in stats['language_pairs'].items():
            print(f"  {pair}: {count}")
        if stats['skip_reasons']:
            print(f"\nSkip reasons:")
            for reason, count in stats['skip_reasons'].items():
                print(f"  {reason}: {count}")

    elif args.action == "import":
        results = d.import_from_all_projects(Path("projects"))
        print("Imported from projects:")
        for proj, count in sorted(results.items()):
            print(f"  {proj}: {count}")
        print(f"\nTotal: {d.stats()['total_words']} words")

    elif args.action == "search":
        if not args.query:
            print("Error: --query required for search")
            sys.exit(1)
        results = d.search(args.query, args.lang, args.target_lang,
                          limit=args.limit, offset=args.offset)
        total = d.count(args.lang, args.target_lang)
        print(f"Found {len(results)} words (total matching: {total}):")
        for w in results:
            skip = " [SKIP]" if w['skip'] else ""
            trans = f" -> {w['translation']}" if w['translation'] else ""
            pair = f"({w['lang']}->{w['translation_lang']})" if w['translation_lang'] else f"({w['lang']})"
            print(f"  {w['word']}{trans} {pair}{skip}")

    elif args.action == "list":
        # List words with pagination
        results = d.list_words(args.lang, args.target_lang,
                              skip_only=args.skip_only,
                              limit=args.limit, offset=args.offset)
        total = d.count(args.lang, args.target_lang, skip_only=args.skip_only)
        print(f"Words {args.offset+1}-{args.offset+len(results)} of {total}:")
        for w in results:
            skip = " [SKIP:" + (w['skip_reason'] or 'manual') + "]" if w['skip'] else ""
            trans = f" -> {w['translation']}" if w['translation'] else ""
            print(f"  {w['word']}{trans}{skip}")

    elif args.action == "skip":
        if not args.word:
            print("Error: --word required for skip")
            sys.exit(1)
        if not args.lang:
            print("Error: --lang required for skip (source language of the word)")
            sys.exit(1)
        reason = args.reason or "manual"
        d.mark_skip(args.word, args.lang, reason, args.target_lang)
        pair = f"{args.lang}->{args.target_lang}" if args.target_lang else args.lang
        print(f"Marked '{args.word}' as skip for {pair} ({reason})")

    elif args.action == "unskip":
        if not args.word:
            print("Error: --word required for unskip")
            sys.exit(1)
        if not args.lang:
            print("Error: --lang required for unskip")
            sys.exit(1)
        d.mark_unskip(args.word, args.lang, args.target_lang)
        pair = f"{args.lang}->{args.target_lang}" if args.target_lang else args.lang
        print(f"Unmarked '{args.word}' from skip for {pair}")

    elif args.action == "show":
        if not args.word:
            print("Error: --word required for show")
            sys.exit(1)
        entry = d.get_word(args.word, args.lang or "es", args.target_lang)
        if entry:
            print(f"Word: {entry['word']}")
            print(f"Language: {entry['lang']} -> {entry['translation_lang']}")
            print(f"Translation: {entry['translation']}")
            print(f"Zipf: {entry['zipf']}")
            print(f"Skip: {bool(entry['skip'])} ({entry['skip_reason']})")
            print(f"Source: {entry['source_project']}")
        else:
            print(f"Word not found: {args.word}")


def cmd_resume(args):
    """Resume existing project pipeline."""
    _start_caffeinate()

    pm = ProjectManager(Path("projects"))

    # Find project
    project = pm.get_project(args.project)
    if not project:
        # Try as path
        project_path = Path(args.project)
        if project_path.exists() and (project_path / "meta.json").exists():
            project = Project.load(project_path)
        else:
            print(f"Error: Project not found: {args.project}")
            sys.exit(1)

    print(f"Resuming project: {project.dir.name}")
    print(f"  Source: {project.meta.source_lang}")
    print(f"  Target: {project.meta.target_lang}")
    print(f"  Sentences: {project.meta.total_sentences}")

    # Show current progress
    print(f"\nCurrent progress:")
    for step, progress in project.meta.progress.items():
        print(f"  [{step}] {progress.done}/{progress.total} ({progress.status.value})")

    # Copy background image if provided
    if args.background:
        bg_path = Path(args.background)
        if not bg_path.exists():
            print(f"Warning: Background image not found: {args.background}")
        else:
            import shutil
            dest = project.video_dir / f"background{bg_path.suffix}"
            shutil.copy(bg_path, dest)
            print(f"Background image: {dest}")

    # Configure pipeline
    width, height = map(int, args.resolution.split("x"))

    # Validate wordcard options compatibility
    wordcard_mode = getattr(args, 'wordcard_mode', 'combined')
    tts_wc_source = getattr(args, 'tts_wordcards_source', None)
    tts_wc_target = getattr(args, 'tts_wordcards_target', None)
    tts_wc = getattr(args, 'tts_wordcards', None)

    if wordcard_mode == "combined" and (tts_wc_source or tts_wc_target):
        print("Error: --tts-wordcards-source and --tts-wordcards-target are only compatible with --wordcard-mode per_word")
        sys.exit(1)

    if wordcard_mode == "per_word" and tts_wc:
        print("Error: --tts-wordcards is only compatible with --wordcard-mode combined")
        print("       Use --tts-wordcards-source and --tts-wordcards-target for per_word mode")
        sys.exit(1)

    # Validate translate_context for OpenAI
    translate_context = getattr(args, 'translate_context', None)
    if args.translator == "openai" and not translate_context:
        print("Error: --translate-context is REQUIRED when using --translator openai")
        print("       Provide context about the text for better translation quality.")
        print("       Example: --translate-context 'Kurt Vonnegut Player Piano - dystopian satire'")
        sys.exit(1)

    config = PipelineConfig(
        source_lang=project.meta.source_lang,
        target_lang=project.meta.target_lang,
        tts_provider=args.tts,
        tts_provider_source=getattr(args, 'tts_source', None),
        tts_provider_target=getattr(args, 'tts_target', None),
        tts_provider_wordcards=tts_wc,
        tts_provider_wordcards_source=tts_wc_source,
        tts_provider_wordcards_target=tts_wc_target,
        translation_provider=args.translator,
        translation_parallel=args.translator_parallel,
        tts_parallel=args.tts_parallel,
        combine_workers=args.combine_workers,
        video_workers=args.video_workers,
        speed_source=args.speed_source,
        speed_target=args.speed_target,
        max_rare_words=args.rare_words,
        font_size=args.font_size,
        video_resolution=(width, height),
        tts_source_locale=args.tts_source_locale,
        tts_target_locale=args.tts_target_locale,
        enable_wordcard_audio=args.enable_wordcard_audio,
        wordcard_mode=wordcard_mode,
        translate_context=translate_context,
    )

    # Show TTS config
    tts_src = config.get_tts_provider_source()
    tts_tgt = config.get_tts_provider_target()
    tts_wc = config.get_tts_provider_wordcards()
    if tts_src == tts_tgt == tts_wc:
        print(f"  TTS: {tts_src} ({config.tts_parallel} threads)")
    else:
        print(f"  TTS: source={tts_src}, target={tts_tgt}, wordcards={tts_wc} ({config.tts_parallel} threads)")

    # Run pipeline (will skip completed steps)
    print(f"\nContinuing pipeline...")

    on_progress = create_progress_callback(print_every=10)
    pipeline = Pipeline(project, config)
    pipeline.run(on_progress)

    # Done
    output = project.get_output_video_path()
    print(f"\nVideo generated: {output}")

    if args.open:
        import subprocess
        subprocess.run(["open", str(output)])


def main():
    parser = argparse.ArgumentParser(
        description="Bilingual video generator - create videos with dual-language subtitles and audio"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # === run command ===
    run_parser = subparsers.add_parser("run", help="Create project from txt and run pipeline")
    run_parser.add_argument("-i", "--input", required=True, help="Input txt file path")
    run_parser.add_argument("-s", "--source", required=True, help="Source language (ru, en, es)")
    run_parser.add_argument("-t", "--target", required=True, help="Target language (ru, en, es)")
    run_parser.add_argument("-n", "--name", help="Project name (default: filename)")
    run_parser.add_argument("--tts", default="google_cloud",
                           choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                           help="TTS provider (default: google_cloud). Use --tts-source/--tts-target/--tts-wordcards for per-step control")
    run_parser.add_argument("--tts-source", default=None,
                           choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                           help="TTS provider for source language (default: same as --tts)")
    run_parser.add_argument("--tts-target", default=None,
                           choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                           help="TTS provider for target language (default: same as --tts)")
    run_parser.add_argument("--tts-wordcards", default=None,
                           choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                           help="TTS provider for word cards in 'combined' mode (default: same as --tts-target)")
    run_parser.add_argument("--tts-wordcards-source", default=None,
                           choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                           help="TTS provider for source translations in wordcards (per_word mode only)")
    run_parser.add_argument("--tts-wordcards-target", default=None,
                           choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                           help="TTS provider for target words in wordcards (per_word mode only)")
    run_parser.add_argument("--translator", default="argos",
                           choices=["google", "deepl-free", "deepl-pro", "argos", "openai", "gemini"],
                           help="Translation provider (default: argos - local, fast, free; openai/gemini - GPT-4o-mini/Gemini for LATAM Spanish)")
    run_parser.add_argument("--translate-context", default=None,
                           help="Context for OpenAI translator (REQUIRED for --translator openai). "
                                "Describe the book/text being translated for better quality. "
                                "Example: 'Kurt Vonnegut Player Piano - dystopian satire about automation'")
    run_parser.add_argument("--translator-parallel", type=int, default=1,
                           help="Parallel translation threads (default: 1, use 4-8 for argos)")
    run_parser.add_argument("--tts-parallel", type=int, default=1,
                           help="Parallel TTS threads (default: 1, use 4 for google_cloud)")
    run_parser.add_argument("--combine-workers", type=int, default=1,
                           help="Parallel workers for audio combine (default: 1, use 8-16 for faster)")
    run_parser.add_argument("--video-workers", type=int, default=1,
                           help="Parallel workers for video encoding (default: 1, use 4-8 for faster)")
    run_parser.add_argument("--speed-source", type=float, default=1.0, help="Source audio speed")
    run_parser.add_argument("--speed-target", type=float, default=1.0, help="Target audio speed")
    run_parser.add_argument("--rare-words", type=int, default=5, help="Max rare words per sentence")
    run_parser.add_argument("--font-size", type=int, default=52, help="Subtitle font size")
    run_parser.add_argument("--resolution", default="1920x1080", help="Video resolution")
    run_parser.add_argument("--tts-source-locale", default=None,
                           help="TTS locale for source (e.g., en-GB for British). See --help-tts-locales")
    run_parser.add_argument("--tts-target-locale", default=None,
                           help="TTS locale for target (e.g., es-latam for Latin American Spanish)")
    run_parser.add_argument("--force", action="store_true", help="Overwrite existing project")
    run_parser.add_argument("--open", action="store_true", help="Open video after generation")
    run_parser.add_argument("--no-split-long", action="store_true",
                           help="Don't split long sentences (keep original sentence boundaries)")
    run_parser.add_argument("--only-sentences", action="store_true",
                           help="Only split text into sentences, skip translation/TTS/video")
    run_parser.add_argument("--only-rare-words", action="store_true",
                           help="Split sentences and extract rare words, skip translation/TTS/video")
    run_parser.add_argument("--stop-after-rare-words", action="store_true",
                           help="Stop after rare words extraction+translation (before TTS/audio/video)")
    run_parser.add_argument("--background", default=None,
                           help="Background image path or 'samename' to find image with same name as input file")
    run_parser.add_argument("--enable-wordcard-audio", action="store_true",
                           help="Generate TTS for rare word cards (target word + source translation)")
    run_parser.add_argument("--wordcard-mode", default="combined",
                           choices=["combined", "per_word"],
                           help="Wordcard audio mode: 'combined' = one TTS request per card (OpenAI style), 'per_word' = separate TTS per word with language tags (Google style)")
    run_parser.set_defaults(func=cmd_run)

    # === list command ===
    list_parser = subparsers.add_parser("list", help="List all projects")
    list_parser.set_defaults(func=cmd_list)

    # === quota command ===
    quota_parser = subparsers.add_parser("quota", help="Show TTS/translation quota usage")
    quota_parser.set_defaults(func=cmd_quota)

    # === dict command ===
    dict_parser = subparsers.add_parser("dict", help="Manage global word dictionary")
    dict_parser.add_argument("action",
                            choices=["stats", "import", "search", "list", "skip", "unskip", "show"],
                            help="Action: stats, import, search, list, skip, unskip, show")
    dict_parser.add_argument("--word", "-w", help="Word to operate on")
    dict_parser.add_argument("--lang", "-l", help="Source language (e.g., es)")
    dict_parser.add_argument("--target-lang", "-t", help="Target language (e.g., ru). For per-language-pair skip")
    dict_parser.add_argument("--reason", "-r",
                            choices=["cognate", "proper_noun", "common", "manual"],
                            help="Skip reason (cognate=similar sound, proper_noun=name/place, common=too frequent)")
    dict_parser.add_argument("--query", "-q", help="Search query (prefix match)")
    dict_parser.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
    dict_parser.add_argument("--offset", type=int, default=0, help="Skip first N results (pagination)")
    dict_parser.add_argument("--skip-only", action="store_true", help="Show only skipped words (for list)")
    dict_parser.set_defaults(func=cmd_dict)

    # === resume command ===
    resume_parser = subparsers.add_parser("resume", help="Resume existing project")
    resume_parser.add_argument("project", help="Project name or path")
    resume_parser.add_argument("--tts", default="google_cloud",
                              choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                              help="TTS provider (default: google_cloud). Use --tts-source/--tts-target/--tts-wordcards for per-step control")
    resume_parser.add_argument("--tts-source", default=None,
                              choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                              help="TTS provider for source language (default: same as --tts)")
    resume_parser.add_argument("--tts-target", default=None,
                              choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                              help="TTS provider for target language (default: same as --tts)")
    resume_parser.add_argument("--tts-wordcards", default=None,
                              choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                              help="TTS provider for word cards in 'combined' mode (default: same as --tts-target)")
    resume_parser.add_argument("--tts-wordcards-source", default=None,
                              choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                              help="TTS provider for source translations in wordcards (per_word mode only)")
    resume_parser.add_argument("--tts-wordcards-target", default=None,
                              choices=["gtts", "google_cloud", "pyttsx3", "openai"],
                              help="TTS provider for target words in wordcards (per_word mode only)")
    resume_parser.add_argument("--translator", default="argos",
                              choices=["google", "deepl-free", "deepl-pro", "argos", "openai", "gemini"],
                              help="Translation provider (default: argos - local, fast, free; openai/gemini - GPT-4o-mini/Gemini for LATAM Spanish)")
    resume_parser.add_argument("--translate-context", default=None,
                              help="Context for OpenAI translator (REQUIRED for --translator openai). "
                                   "Describe the book/text being translated for better quality.")
    resume_parser.add_argument("--translator-parallel", type=int, default=1,
                              help="Parallel translation threads (default: 1, use 4-8 for argos)")
    resume_parser.add_argument("--tts-parallel", type=int, default=1,
                              help="Parallel TTS threads (default: 1, use 4 for google_cloud)")
    resume_parser.add_argument("--combine-workers", type=int, default=1,
                              help="Parallel workers for audio combine (default: 1, use 8-16 for faster)")
    resume_parser.add_argument("--video-workers", type=int, default=1,
                              help="Parallel workers for video encoding (default: 1, use 4-8 for faster)")
    resume_parser.add_argument("--speed-source", type=float, default=1.0, help="Source audio speed")
    resume_parser.add_argument("--speed-target", type=float, default=1.0, help="Target audio speed")
    resume_parser.add_argument("--rare-words", type=int, default=5, help="Max rare words per sentence")
    resume_parser.add_argument("--font-size", type=int, default=52, help="Subtitle font size")
    resume_parser.add_argument("--resolution", default="1920x1080", help="Video resolution")
    resume_parser.add_argument("--tts-source-locale", default=None,
                              help="TTS locale for source (e.g., en-GB for British)")
    resume_parser.add_argument("--tts-target-locale", default=None,
                              help="TTS locale for target (e.g., es-latam for Latin American Spanish)")
    resume_parser.add_argument("--background", default=None,
                              help="Background image path (png/jpg). Copied to project/video/background.*")
    resume_parser.add_argument("--enable-wordcard-audio", action="store_true",
                              help="Generate TTS for rare word cards (target word + source translation)")
    resume_parser.add_argument("--wordcard-mode", default="combined",
                              choices=["combined", "per_word"],
                              help="Wordcard audio mode: 'combined' = one TTS request per card (OpenAI style), 'per_word' = separate TTS per word with language tags (Google style)")
    resume_parser.add_argument("--open", action="store_true", help="Open video after generation")
    resume_parser.set_defaults(func=cmd_resume)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
