#!/usr/bin/env python3
"""
Generate thumbnails for all books with background images.

Usage:
    python scripts/generate_thumbnails.py [output_dir]

Example:
    python scripts/generate_thumbnails.py                    # -> thumbnails/
    python scripts/generate_thumbnails.py ~/my_thumbnails    # -> custom dir
"""

import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from video.thumbnail_variants import prepare_background, variant_13, load_fonts
from PIL import ImageDraw

# Book info mapping: filename_stem -> (author_en, title_en, author_ru, title_ru)
BOOK_INFO = {
    # Asimov
    "asimov_bicentennial_man": ("Isaac Asimov", "The Bicentennial Man", "Айзек Азимов", "Двухсотлетний человек"),
    "asimov_caves_of_steel": ("Isaac Asimov", "The Caves of Steel", "Айзек Азимов", "Стальные пещеры"),
    "asimov_horovod": ("Isaac Asimov", "Runaround", "Айзек Азимов", "Хоровод"),
    "asimov_nightfall": ("Isaac Asimov", "Nightfall", "Айзек Азимов", "Приход ночи"),
    "asimov_profession": ("Isaac Asimov", "Profession", "Айзек Азимов", "Профессия"),
    "asimov_last_question": ("Isaac Asimov", "The Last Question", "Айзек Азимов", "Последний вопрос"),
    "asimov_ugly_boy": ("Isaac Asimov", "The Ugly Little Boy", "Айзек Азимов", "Уродливый мальчуган"),

    # Bacigalupi
    "bacigalupi_flute": ("Paolo Bacigalupi", "The Fluted Girl", "Паоло Бачигалупи", "Девочка-флейта"),
    "bacigalupi_pop": ("Paolo Bacigalupi", "Pop Squad", "Паоло Бачигалупи", "Специалист по калориям"),
    "bacigalupi_pump": ("Paolo Bacigalupi", "The People of Sand and Slag", "Паоло Бачигалупи", "Народ песка и шлака"),
    "bacigalupi_sand": ("Paolo Bacigalupi", "The Tamarisk Hunter", "Паоло Бачигалупи", "Охотник за тамариском"),

    # Belyaev
    "belyaev_amphibian": ("Alexander Belyaev", "Amphibian Man", "Александр Беляев", "Человек-амфибия"),
    "belyaev_ariel": ("Alexander Belyaev", "Ariel", "Александр Беляев", "Ариэль"),
    "belyaev_douel": ("Alexander Belyaev", "Professor Dowell's Head", "Александр Беляев", "Голова профессора Доуэля"),

    # Bethke
    "bethke_cyberpunk": ("Bruce Bethke", "Cyberpunk", "Брюс Бетке", "Киберпанк"),

    # Borges
    "borges_ragnarek": ("Jorge Luis Borges", "Ragnarök", "Хорхе Луис Борхес", "Рагнарёк"),
    "borges_yug": ("Jorge Luis Borges", "The South", "Хорхе Луис Борхес", "Юг"),
    "borges_library": ("Jorge Luis Borges", "The Library of Babel", "Хорхе Луис Борхес", "Вавилонская библиотека"),
    "borges_garden": ("Jorge Luis Borges", "Garden of Forking Paths", "Хорхе Луис Борхес", "Сад расходящихся тропок"),

    # Bradbury
    "bradbury_morning": ("Ray Bradbury", "The Fog Horn", "Рэй Брэдбери", "Ревун"),
    "bradbury_rain": ("Ray Bradbury", "The Long Rain", "Рэй Брэдбери", "Долгий дождь"),
    "bradbury_thunder": ("Ray Bradbury", "A Sound of Thunder", "Рэй Брэдбери", "И грянул гром"),
    "bradbury_soft_rains": ("Ray Bradbury", "There Will Come Soft Rains", "Рэй Брэдбери", "Будет ласковый дождь"),
    "bradbury_pedestrian": ("Ray Bradbury", "The Pedestrian", "Рэй Брэдбери", "Пешеход"),

    # Collections
    "british_tales": ("Various Authors", "British Ghost Tales", "Разные авторы", "Британские рассказы о призраках"),
    "cyberpunk_anthology": ("Various Authors", "Cyberpunk Anthology", "Разные авторы", "Антология киберпанка"),
    "japanese_10nights": ("Natsume Sōseki", "Ten Nights of Dreams", "Нацумэ Сосэки", "Десять снов"),
    "japanese_tales": ("Various Authors", "Japanese Ghost Stories", "Разные авторы", "Японские истории о призраках"),

    # Chekhov
    "chekhov_o_lyubvi": ("Anton Chekhov", "About Love", "Антон Чехов", "О любви"),

    # Chiang
    "chiang_division": ("Ted Chiang", "Division by Zero", "Тед Чан", "Деление на ноль"),
    "chiang_like": ("Ted Chiang", "Liking What You See", "Тед Чан", "Тебе нравится, что ты видишь?"),
    "chiang_understand": ("Ted Chiang", "Understand", "Тед Чан", "Понимай"),
    "chiang_story": ("Ted Chiang", "Story of Your Life", "Тед Чан", "История твоей жизни"),
    "chiang_tower": ("Ted Chiang", "Tower of Babylon", "Тед Чан", "Вавилонская башня"),

    # Clarke
    "clarke_sentinel": ("Arthur C. Clarke", "The Sentinel", "Артур Кларк", "Часовой"),
    "clarke_wind": ("Arthur C. Clarke", "The Wind from the Sun", "Артур Кларк", "Солнечный ветер"),
    "clarke_star": ("Arthur C. Clarke", "The Star", "Артур Кларк", "Звезда"),
    "clarke_nine_billion": ("Arthur C. Clarke", "The Nine Billion Names of God", "Артур Кларк", "Девять миллиардов имён Бога"),

    # Cortazar
    "cortazar_aksolotl": ("Julio Cortázar", "Axolotl", "Хулио Кортасар", "Аксолотль"),
    "cortazar_slyuni": ("Julio Cortázar", "Letter to a Young Lady", "Хулио Кортасар", "Письмо в Париж одной сеньорите"),

    # Gibson
    "gibson_agrippa": ("William Gibson", "Agrippa", "Уильям Гибсон", "Агриппа"),
    "gibson_backwater": ("William Gibson", "Hinterlands", "Уильям Гибсон", "Захолустье"),
    "gibson_doll": ("William Gibson", "The Winter Market", "Уильям Гибсон", "Зимний рынок"),
    "gibson_johnny": ("William Gibson", "Johnny Mnemonic", "Уильям Гибсон", "Джонни-мнемоник"),
    "gibson_burning": ("William Gibson", "Burning Chrome", "Уильям Гибсон", "Сожжение Хром"),

    # Lovecraft
    "lovecraft_crypt": ("H.P. Lovecraft", "In the Vault", "Говард Лавкрафт", "В склепе"),
    "lovecraft_dagon": ("H.P. Lovecraft", "Dagon", "Говард Лавкрафт", "Дагон"),
    "lovecraft_zann": ("H.P. Lovecraft", "The Music of Erich Zann", "Говард Лавкрафт", "Музыка Эриха Цанна"),
    "lovecraft_call": ("H.P. Lovecraft", "The Call of Cthulhu", "Говард Лавкрафт", "Зов Ктулху"),

    # O. Henry
    "ohenry_last_leaf": ("O. Henry", "The Last Leaf", "О. Генри", "Последний лист"),
    "ohenry_gift": ("O. Henry", "The Gift of the Magi", "О. Генри", "Дары волхвов"),

    # Poe
    "poe_purloined_letter": ("Edgar Allan Poe", "The Purloined Letter", "Эдгар Аллан По", "Похищенное письмо"),
    "poe_rue_morgue": ("Edgar Allan Poe", "Murders in the Rue Morgue", "Эдгар Аллан По", "Убийство на улице Морг"),
    "poe_raven": ("Edgar Allan Poe", "The Raven", "Эдгар Аллан По", "Ворон"),
    "poe_tell_tale": ("Edgar Allan Poe", "The Tell-Tale Heart", "Эдгар Аллан По", "Сердце-обличитель"),

    # Sheckley
    "sheckley_absolute": ("Robert Sheckley", "The Absolute Weapon", "Роберт Шекли", "Абсолютное оружие"),
    "sheckley_ticket": ("Robert Sheckley", "Ticket to Tranai", "Роберт Шекли", "Билет на планету Транай"),
    "sheckley_odor": ("Robert Sheckley", "The Odor of Thought", "Роберт Шекли", "Запах мысли"),
    "sheckley_prize": ("Robert Sheckley", "The Prize of Peril", "Роберт Шекли", "Премия за риск"),
    "Абсолютное оружие": ("Robert Sheckley", "The Absolute Weapon", "Роберт Шекли", "Абсолютное оружие"),
    "Билет на планету Транай": ("Robert Sheckley", "Ticket to Tranai", "Роберт Шекли", "Билет на планету Транай"),

    # Silverberg
    "silverberg_invisible_man": ("Robert Silverberg", "To See the Invisible Man", "Роберт Сильверберг", "Увидеть невидимку"),
    "silverberg_passengers": ("Robert Silverberg", "Passengers", "Роберт Сильверберг", "Пассажиры"),

    # Simak
    "simak_armistice": ("Clifford Simak", "The Big Front Yard", "Клиффорд Саймак", "Большой двор"),
    "simak_brother": ("Clifford Simak", "Brother", "Клиффорд Саймак", "Братья"),
    "simak_money_tree": ("Clifford Simak", "The Money Tree", "Клиффорд Саймак", "Денежное дерево"),
    "simak_razvedka": ("Clifford Simak", "Desertion", "Клиффорд Саймак", "Дезертирство"),
    "simak_svalka": ("Clifford Simak", "Junkyard", "Клиффорд Саймак", "Свалка"),

    # Sterling
    "sterling_black_swan": ("Bruce Sterling", "Black Swan", "Брюс Стерлинг", "Чёрный лебедь"),
    "sterling_holy_fire": ("Bruce Sterling", "Holy Fire", "Брюс Стерлинг", "Священный огонь"),
    "sterling_maneki": ("Bruce Sterling", "Maneki Neko", "Брюс Стерлинг", "Манеки-неко"),
    "sterling_roy": ("Bruce Sterling", "Our Neural Chernobyl", "Брюс Стерлинг", "Наш нейронный Чернобыль"),
    "sterling_schismatrix": ("Bruce Sterling", "Schismatrix", "Брюс Стерлинг", "Схизматрица"),
    "sterling_swarm": ("Bruce Sterling", "Swarm", "Брюс Стерлинг", "Рой"),

    # Stross
    "stross_cold_war": ("Charles Stross", "A Colder War", "Чарльз Стросс", "Холодная война"),
    "stross_palimpsest": ("Charles Stross", "Palimpsest", "Чарльз Стросс", "Палимпсест"),

    # Tyurin
    "tyurin_koschei": ("Alexander Tyurin", "Koschei the Deathless", "Александр Тюрин", "Кощей Бессмертный"),

    # Watts
    "watts_colonel": ("Peter Watts", "The Colonel", "Питер Уоттс", "Полковник"),
    "watts_island": ("Peter Watts", "The Island", "Питер Уоттс", "Остров"),

    # Wells
    "wells_time_machine": ("H.G. Wells", "The Time Machine", "Герберт Уэллс", "Машина времени"),
    "wells_war_of_worlds": ("H.G. Wells", "The War of the Worlds", "Герберт Уэллс", "Война миров"),

    # Zelazny
    "zelazny_fayoli": ("Roger Zelazny", "A Rose for Ecclesiastes", "Роджер Желязны", "Роза для Екклезиаста"),

    # Nabokov
    "nabokov_uzhas": ("Vladimir Nabokov", "Terror", "Владимир Набоков", "Ужас"),

    # Vonnegut - Player Piano chapters
    "vonnegut_piano_ch01": ("Kurt Vonnegut", "Player Piano Ch.1", "Курт Воннегут", "Механическое пианино гл.1"),
    "vonnegut_piano_ch02": ("Kurt Vonnegut", "Player Piano Ch.2", "Курт Воннегут", "Механическое пианино гл.2"),
    "vonnegut_piano_ch03": ("Kurt Vonnegut", "Player Piano Ch.3", "Курт Воннегут", "Механическое пианино гл.3"),
    "vonnegut_piano_ch04": ("Kurt Vonnegut", "Player Piano Ch.4", "Курт Воннегут", "Механическое пианино гл.4"),
    "vonnegut_piano_ch05": ("Kurt Vonnegut", "Player Piano Ch.5", "Курт Воннегут", "Механическое пианино гл.5"),
    "vonnegut_piano_ch06": ("Kurt Vonnegut", "Player Piano Ch.6", "Курт Воннегут", "Механическое пианино гл.6"),
    "vonnegut_piano_ch07": ("Kurt Vonnegut", "Player Piano Ch.7", "Курт Воннегут", "Механическое пианино гл.7"),
    "vonnegut_piano_ch08": ("Kurt Vonnegut", "Player Piano Ch.8", "Курт Воннегут", "Механическое пианино гл.8"),
    "vonnegut_piano_ch09": ("Kurt Vonnegut", "Player Piano Ch.9", "Курт Воннегут", "Механическое пианино гл.9"),
    "vonnegut_piano_ch10": ("Kurt Vonnegut", "Player Piano Ch.10", "Курт Воннегут", "Механическое пианино гл.10"),
    "vonnegut_piano_ch11": ("Kurt Vonnegut", "Player Piano Ch.11", "Курт Воннегут", "Механическое пианино гл.11"),
    "vonnegut_piano_ch12": ("Kurt Vonnegut", "Player Piano Ch.12", "Курт Воннегут", "Механическое пианино гл.12"),
    "vonnegut_piano_ch13": ("Kurt Vonnegut", "Player Piano Ch.13", "Курт Воннегут", "Механическое пианино гл.13"),
    "vonnegut_piano_ch14": ("Kurt Vonnegut", "Player Piano Ch.14", "Курт Воннегут", "Механическое пианино гл.14"),
    "vonnegut_piano_ch15": ("Kurt Vonnegut", "Player Piano Ch.15", "Курт Воннегут", "Механическое пианино гл.15"),
    "vonnegut_piano_ch16": ("Kurt Vonnegut", "Player Piano Ch.16", "Курт Воннегут", "Механическое пианино гл.16"),
    "vonnegut_piano_ch17": ("Kurt Vonnegut", "Player Piano Ch.17", "Курт Воннегут", "Механическое пианино гл.17"),
    "vonnegut_piano_ch18": ("Kurt Vonnegut", "Player Piano Ch.18", "Курт Воннегут", "Механическое пианино гл.18"),
    "vonnegut_piano_ch19": ("Kurt Vonnegut", "Player Piano Ch.19", "Курт Воннегут", "Механическое пианино гл.19"),
    "vonnegut_piano_ch20": ("Kurt Vonnegut", "Player Piano Ch.20", "Курт Воннегут", "Механическое пианино гл.20"),
    "vonnegut_piano_ch21": ("Kurt Vonnegut", "Player Piano Ch.21", "Курт Воннегут", "Механическое пианино гл.21"),
    "vonnegut_piano_ch22": ("Kurt Vonnegut", "Player Piano Ch.22", "Курт Воннегут", "Механическое пианино гл.22"),
    "vonnegut_piano_ch23": ("Kurt Vonnegut", "Player Piano Ch.23", "Курт Воннегут", "Механическое пианино гл.23"),
    "vonnegut_piano_ch24": ("Kurt Vonnegut", "Player Piano Ch.24", "Курт Воннегут", "Механическое пианино гл.24"),
    "vonnegut_piano_ch25": ("Kurt Vonnegut", "Player Piano Ch.25", "Курт Воннегут", "Механическое пианино гл.25"),
    "vonnegut_piano_ch26": ("Kurt Vonnegut", "Player Piano Ch.26", "Курт Воннегут", "Механическое пианино гл.26"),
    "vonnegut_piano_ch27": ("Kurt Vonnegut", "Player Piano Ch.27", "Курт Воннегут", "Механическое пианино гл.27"),
    "vonnegut_piano_ch28": ("Kurt Vonnegut", "Player Piano Ch.28", "Курт Воннегут", "Механическое пианино гл.28"),
    "vonnegut_piano_ch29": ("Kurt Vonnegut", "Player Piano Ch.29", "Курт Воннегут", "Механическое пианино гл.29"),
    "vonnegut_piano_ch30": ("Kurt Vonnegut", "Player Piano Ch.30", "Курт Воннегут", "Механическое пианино гл.30"),
    "vonnegut_piano_ch31": ("Kurt Vonnegut", "Player Piano Ch.31", "Курт Воннегут", "Механическое пианино гл.31"),
    "vonnegut_piano_ch32": ("Kurt Vonnegut", "Player Piano Ch.32", "Курт Воннегут", "Механическое пианино гл.32"),
    "vonnegut_piano_ch33": ("Kurt Vonnegut", "Player Piano Ch.33", "Курт Воннегут", "Механическое пианино гл.33"),
    "vonnegut_piano_ch34": ("Kurt Vonnegut", "Player Piano Ch.34", "Курт Воннегут", "Механическое пианино гл.34"),
    "vonnegut_piano_ch35": ("Kurt Vonnegut", "Player Piano Ch.35", "Курт Воннегут", "Механическое пианино гл.35"),
}

SKIP = ["TEST"]


def generate_thumbnails(source_dir: Path, output_dir: Path, target_lang: str = "LATAM SPANISH"):
    """Generate thumbnails for all books with images."""
    fonts = load_fonts()
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    errors = []

    # Find all PNG files recursively
    all_images = list(source_dir.rglob("*.png"))
    print(f"Found {len(all_images)} images\n")

    for img_file in sorted(all_images):
        name = img_file.stem
        if name in SKIP:
            continue

        # Get author/title info
        if name in BOOK_INFO:
            author_en, title_en, author_ru, title_ru = BOOK_INFO[name]
        else:
            # Unknown book - skip or use filename
            print(f"⚠️  Unknown book: {name} - skipping")
            continue

        try:
            img = prepare_background(img_file)
            draw = ImageDraw.Draw(img)

            img = variant_13(
                img, draw, fonts,
                author_en=author_en,
                title_en=title_en,
                src_lang="RUSSIAN",
                tgt_lang=target_lang,
                title_ru=title_ru,
                author_ru=author_ru
            )
            img = img.convert('RGB')

            out_path = output_dir / f"{name}.png"
            img.save(str(out_path), quality=95)
            print(f"✓ {name}")
            count += 1
        except Exception as e:
            print(f"❌ {name}: {e}")
            errors.append((name, str(e)))

    print(f"\n{'='*50}")
    print(f"Generated {count} thumbnails in {output_dir}")
    if errors:
        print(f"Errors: {len(errors)}")
        for name, err in errors:
            print(f"  - {name}: {err}")

    return count, errors


if __name__ == "__main__":
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "thumbnails"
    source_dir = PROJECT_ROOT / "txt_source"

    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        sys.exit(1)

    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print(f"{'='*50}\n")

    generate_thumbnails(source_dir, output_dir)
