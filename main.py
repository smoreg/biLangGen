#!/usr/bin/env python3
"""Bilingual video generator CLI.

Usage:
    python main.py run -i txt_source/TEST.txt -s ru -t es
    python main.py list
    python main.py resume TEST_ru_es --open
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from project import Project, ProjectManager, Pipeline, PipelineConfig
from utils.progress import create_progress_callback


def cmd_run(args):
    """Create project from txt file and run full pipeline."""
    # 1. Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # 2. Determine project name
    name = args.name or input_path.stem

    # 3. Create or load project
    pm = ProjectManager(Path("projects"))
    slug = f"{name}_{args.source}_{args.target}"

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

    # 5. Configure pipeline
    width, height = map(int, args.resolution.split("x"))
    if args.only_sentences:
        stop_after = "sentences"
    elif args.only_rare_words:
        stop_after = "rare_words_extract"
    else:
        stop_after = None
    config = PipelineConfig(
        source_lang=args.source,
        target_lang=args.target,
        tts_provider=args.tts,
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
    )

    print(f"\nPipeline config:")
    print(f"  TTS: {config.tts_provider} ({config.tts_parallel} threads)")
    if config.tts_source_locale or config.tts_target_locale:
        src_loc = config.tts_source_locale or args.source
        tgt_loc = config.tts_target_locale or args.target
        print(f"  TTS locales: {src_loc} / {tgt_loc}")
    print(f"  Translator: {config.translation_provider} ({config.translation_parallel} threads)")
    print(f"  Languages: {args.source} -> {args.target}")
    print(f"  Resolution: {args.resolution}")

    # 6. Run pipeline
    print(f"\nRunning pipeline...")

    on_progress = create_progress_callback(print_every=10)
    pipeline = Pipeline(project, config)
    pipeline.run(on_progress)

    # 7. Done
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


def cmd_resume(args):
    """Resume existing project pipeline."""
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

    # Configure pipeline
    width, height = map(int, args.resolution.split("x"))
    config = PipelineConfig(
        source_lang=project.meta.source_lang,
        target_lang=project.meta.target_lang,
        tts_provider=args.tts,
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
    )

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
                           choices=["gtts", "google_cloud", "pyttsx3"],
                           help="TTS provider (default: google_cloud)")
    run_parser.add_argument("--translator", default="argos",
                           choices=["google", "deepl-free", "deepl-pro", "argos", "openai"],
                           help="Translation provider (default: argos - local, fast, free; openai - GPT-4o-mini for LATAM Spanish)")
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
    run_parser.add_argument("--only-sentences", action="store_true",
                           help="Only split text into sentences, skip translation/TTS/video")
    run_parser.add_argument("--only-rare-words", action="store_true",
                           help="Split sentences and extract rare words, skip translation/TTS/video")
    run_parser.set_defaults(func=cmd_run)

    # === list command ===
    list_parser = subparsers.add_parser("list", help="List all projects")
    list_parser.set_defaults(func=cmd_list)

    # === quota command ===
    quota_parser = subparsers.add_parser("quota", help="Show TTS/translation quota usage")
    quota_parser.set_defaults(func=cmd_quota)

    # === resume command ===
    resume_parser = subparsers.add_parser("resume", help="Resume existing project")
    resume_parser.add_argument("project", help="Project name or path")
    resume_parser.add_argument("--tts", default="google_cloud",
                              choices=["gtts", "google_cloud", "pyttsx3"],
                              help="TTS provider (default: google_cloud)")
    resume_parser.add_argument("--translator", default="argos",
                              choices=["google", "deepl-free", "deepl-pro", "argos", "openai"],
                              help="Translation provider (default: argos - local, fast, free; openai - GPT-4o-mini for LATAM Spanish)")
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
    resume_parser.add_argument("--open", action="store_true", help="Open video after generation")
    resume_parser.set_defaults(func=cmd_resume)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
