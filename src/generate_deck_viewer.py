from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from mtg_collection_utils import ensure_columns, read_csv_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a local interactive HTML deck viewer from a deck JSON file and an enriched collection CSV."
    )
    parser.add_argument("--deck", required=True, help="Path to a deck JSON definition.")
    parser.add_argument("--collection", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument("--output", required=True, help="Path to the generated HTML file.")
    return parser.parse_args()


def slugify_card_name(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def build_scryfall_image_url(card_id: str) -> str:
    clean = card_id.strip().lower()
    return f"https://cards.scryfall.io/normal/front/{clean[0]}/{clean[1]}/{clean}.jpg"


def build_scryfall_page_url(row: pd.Series) -> str:
    set_code = str(row.get("Set code", "")).strip().lower()
    collector_number = str(row.get("Collector number", "")).strip().lower()
    name = str(row.get("Name", "")).strip()
    if set_code and collector_number and name:
        slug = slugify_card_name(name)
        return f"https://scryfall.com/card/{set_code}/{collector_number}/{slug}"

    card_id = str(row.get("Scryfall ID", "")).strip()
    if card_id and card_id.lower() != "nan":
        return f"https://api.scryfall.com/cards/{card_id}"

    return ""


def build_scryfall_search_url(name: str) -> str:
    return f"https://scryfall.com/search?q={quote('!' + chr(34) + name + chr(34))}"


def build_cardmarket_search_url(name: str) -> str:
    return f"https://www.cardmarket.com/en/Magic/Products/Search?searchString={quote(name.strip())}"


def derive_tags(card: dict) -> list[str]:
    category = str(card.get("category", ""))
    type_line = str(card.get("type_line", "") or "")
    oracle_text = str(card.get("oracle_text", "") or "")
    mana_cost = str(card.get("mana_cost", "") or "")
    combined = f"{type_line}\n{oracle_text}".lower()

    tags: list[str] = []

    if category == "Commander":
        tags.append("Commander")
    if "faerie" in combined:
        tags.append("Faerie")
    if "rogue" in combined:
        tags.append("Rogue")
    if "changeling" in combined:
        tags.append("Changeling")
    if "flash" in combined or "as though it had flash" in combined:
        tags.append("Flash")
    if "counter target" in combined:
        tags.append("Counter")
    if "destroy target" in combined or "exile target" in combined or "target player sacrifices" in combined:
        tags.append("Removal")
    if "return target" in combined or "owner's hand" in combined:
        tags.append("Bounce")
    if "draw" in combined:
        tags.append("Draw")
    if "add {c}" in combined or "add one mana" in combined or "search your library for a basic land" in combined:
        tags.append("Ramp")
    if "return target creature card from your graveyard" in combined or "return target creature card" in combined:
        tags.append("Recursion")
    if "goad" in combined:
        tags.append("Goad")
    if "other faerie creatures you control get" in combined or "other creatures you control with flying get" in combined:
        tags.append("Anthem")
    if "create a 1/1" in combined or "create two 1/1" in combined:
        tags.append("Tokens")
    if not tags and mana_cost:
        tags.append("Support")

    return tags[:4]


def parse_mana_value(mana_cost: str) -> int:
    if not mana_cost:
        return 0

    total = 0
    for symbol in re.findall(r"\{([^}]+)\}", mana_cost):
        if symbol.isdigit():
            total += int(symbol)
        elif "/" in symbol:
            total += 1
        elif symbol.upper() in {"X", "Y", "Z"}:
            total += 0
        else:
            total += 1
    return total


COLOR_ORDER = ["W", "U", "B", "R", "G"]
COLOR_LABELS = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}


def split_color_identity(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def derive_mana_source_colors(card: dict) -> list[str]:
    oracle_text = str(card.get("oracle_text", "") or "")
    found: list[str] = []
    for color in COLOR_ORDER:
        if f"{{{color}}}" in oracle_text and color not in found:
            found.append(color)
    return found


CUSTOM_SYNERGY_LOOKUP = {
    "Alela, Cunning Conqueror": {
        "summary": "Alela ties the whole deck together: cheap interaction on opponents' turns makes Faeries, then evasive chip damage converts into board control through goad.",
        "related": ["Spellstutter Sprite", "Dreamspoiler Witches", "Faerie Tauntings", "Skullclamp", "Mistbind Clique"],
    },
    "Spellstutter Sprite": {
        "summary": "This scales directly with Alela's token production. As the Faerie count rises, it shifts from an early tempo piece into a real permission engine.",
        "related": ["Alela, Cunning Conqueror", "Scion of Oona", "Mistbind Clique", "Maskwood Nexus", "Faerie Harbinger"],
    },
    "Scion of Oona": {
        "summary": "Scion protects the token swarm and turns small flyers into meaningful pressure without asking you to tap out in your own turn.",
        "related": ["Alela, Cunning Conqueror", "Spellstutter Sprite", "Mistbind Clique", "Thunderclap Wyvern", "Sprite Noble"],
    },
    "Dreamspoiler Witches": {
        "summary": "One of the clearest commander's-turn payoffs in the list. Every instant-speed spell becomes board control once this sticks.",
        "related": ["Alela, Cunning Conqueror", "Think Twice", "Counterspell", "Peppersmoke", "Faerie Tauntings"],
    },
    "Glen Elendra Pranksters": {
        "summary": "Turns your reactive play pattern into recursion. Flash creatures and ETB Faeries become much more annoying once you can pick them back up repeatedly.",
        "related": ["Spellstutter Sprite", "Faerie Harbinger", "Aven Mindcensor", "Whitemane Lion", "Stonecloaker"],
    },
    "Mistbind Clique": {
        "summary": "Alela's tokens give you disposable Faeries to champion, which makes Mistbind much easier to deploy as a real mana-denial swing.",
        "related": ["Alela, Cunning Conqueror", "Spellstutter Sprite", "Scion of Oona", "Maskwood Nexus", "Faerie Conclave"],
    },
    "Faerie Harbinger": {
        "summary": "Harbinger smooths draws by setting up your best tribal payoff and plays nicely with bounce effects for repeated tutoring.",
        "related": ["Spellstutter Sprite", "Mistbind Clique", "Whitemane Lion", "Stonecloaker", "Familiar's Ruse"],
    },
    "Voracious Tome-Skimmer": {
        "summary": "A cheap payoff for doing the Alela thing. It rewards you for keeping mana open and spending it on each opponent's turn.",
        "related": ["Alela, Cunning Conqueror", "Think Twice", "Counterspell", "Spell Pierce", "Faerie Tauntings"],
    },
    "Mirror Entity": {
        "summary": "This is your cleanest board-wide finisher. It converts random Faerie tokens and support creatures into a lethal attack step.",
        "related": ["Alela, Cunning Conqueror", "Scion of Oona", "Thunderclap Wyvern", "Sprite Noble", "Cover of Darkness"],
    },
    "Skullclamp": {
        "summary": "Alela's 1/1 tokens make Skullclamp one of the best engines in the deck. It turns extra Faeries into real velocity.",
        "related": ["Alela, Cunning Conqueror", "Faerie Tauntings", "Distant Melody", "Maskwood Nexus", "Sword of Fire and Ice"],
    },
    "Maskwood Nexus": {
        "summary": "This amplifies almost every tribal interaction in the list by making your creatures and tokens count as Faeries all the time.",
        "related": ["Spellstutter Sprite", "Mistbind Clique", "Crib Swap", "Nameless Inversion", "Mutavault"],
    },
    "Faerie Tauntings": {
        "summary": "This turns the deck's reactive posture into an actual clock. Holding up mana now advances both your board and life-total pressure.",
        "related": ["Alela, Cunning Conqueror", "Dreamspoiler Witches", "Think Twice", "Counterspell", "Voracious Tome-Skimmer"],
    },
    "Familiar's Ruse": {
        "summary": "The drawback is often an upside here because the deck is full of creatures with useful enters-the-battlefield effects and tribal counts worth reusing.",
        "related": ["Spellstutter Sprite", "Faerie Harbinger", "Aven Mindcensor", "Whitemane Lion", "Stonecloaker"],
    },
    "Whitemane Lion": {
        "summary": "This is both an instant-speed trigger for Alela and a way to loop your best ETB creatures without spending a full card.",
        "related": ["Alela, Cunning Conqueror", "Spellstutter Sprite", "Faerie Harbinger", "Sower of Temptation", "Familiar's Ruse"],
    },
    "Stonecloaker": {
        "summary": "A flexible trick that protects your board, recycles ETB creatures, and incidentally checks graveyards while still playing at flash speed.",
        "related": ["Spellstutter Sprite", "Faerie Harbinger", "Sower of Temptation", "Whitemane Lion", "Necromancy"],
    },
    "Sower of Temptation": {
        "summary": "Stealing a key creature is already strong, and the bounce/blink package gives you extra ways to reuse the effect or protect Sower.",
        "related": ["Whitemane Lion", "Stonecloaker", "Momentary Blink", "Necromancy", "Alela, Cunning Conqueror"],
    },
    "Distant Melody": {
        "summary": "The deck can flood the board with Faeries over several turns, so this often turns into a major refill spell rather than a medium tribal draw piece.",
        "related": ["Alela, Cunning Conqueror", "Skullclamp", "Maskwood Nexus", "Scion of Oona", "Mirror Entity"],
    },
    "Cloak and Dagger": {
        "summary": "Rogue typing matters because Alela makes Faerie Rogue tokens. This lets the equipment slide onto the creatures that are already connecting in combat.",
        "related": ["Alela, Cunning Conqueror", "Oona's Blackguard", "Dauthi Voidwalker", "Sword of Fire and Ice", "Cover of Darkness"],
    },
    "Sword of Fire and Ice": {
        "summary": "Your evasive board makes this unusually reliable. Small Faeries become real threats and the on-hit trigger compounds your tempo lead.",
        "related": ["Alela, Cunning Conqueror", "Cloak and Dagger", "Cover of Darkness", "Scion of Oona", "Mirror Entity"],
    },
    "Cover of Darkness": {
        "summary": "A classic tribal closer. Giving the chosen tribe evasion means your token swarm actually ends games instead of just pecking at life totals.",
        "related": ["Alela, Cunning Conqueror", "Mirror Entity", "Sword of Fire and Ice", "Oona's Blackguard", "Sprite Noble"],
    },
    "Mutavault": {
        "summary": "This supports tribal math at very low deckbuilding cost and can become a Faerie body exactly when you need another count or attacker.",
        "related": ["Spellstutter Sprite", "Mistbind Clique", "Maskwood Nexus", "Scion of Oona", "Faerie Conclave"],
    },
    "Faerie Conclave": {
        "summary": "A mana source that also becomes a Faerie helps the deck play long games without flooding on purely passive lands.",
        "related": ["Spellstutter Sprite", "Mistbind Clique", "Scion of Oona", "Sprite Noble", "Mutavault"],
    },
}


CUSTOM_REASON_LOOKUP = {
    "Alela, Cunning Conqueror": "The commander rewards playing on each opponent's turn. The whole shell is built to hold up cheap interaction, generate Faerie tokens at instant speed, and convert evasive chip damage into goad pressure.",
    "Spellstutter Sprite": "One of the cleanest tribal payoff cards here. Alela's tokens increase the counter range quickly, so this scales from early interaction into a real soft lock piece.",
    "Scion of Oona": "Flash keeps it on-plan with Alela, and the anthem plus protection effect makes your Faerie tokens much harder to pick off while improving combat.",
    "Dreamspoiler Witches": "This is a true payoff card for the commander. Once you are casting on opponents' turns, it turns routine interaction into repeatable creature shrink and picks off utility bodies.",
    "Glen Elendra Pranksters": "Alela likes creatures with enter-the-battlefield value and flash timing. This lets your instant-speed turns also rebuy Spellstutter Sprite, Aven Mindcensor, or other utility creatures.",
    "Mistbind Clique": "A major tribal tempo play. Alela's Faerie tokens make the champion clause easier to support, and this can time-walk an opponent by tying up their mana at the right moment.",
    "Sower of Temptation": "Fits the evasive Faerie plan while acting as swingy creature control. Blink and bounce effects can help reuse it if needed.",
    "Voracious Tome-Skimmer": "Alela naturally asks you to cast spells on opponents' turns, so this turns that play pattern into extra cards at a very low opportunity cost.",
    "Oona's Blackguard": "Your token stream gives you many small evasive attackers, which means this can snowball hand pressure and make combat damage matter more than it normally would.",
    "Faerie Harbinger": "A tribal tutor with flash. It can find your best payoff or the right Faerie for the current board state while still triggering an instant-speed game plan.",
    "Wydwen, the Biting Gale": "A resilient flash threat that keeps mana open and plays well in a reactive shell. It contributes to the Faerie count without forcing you to tap out.",
    "Aven Mindcensor": "This is classic hold-up interaction. It punishes tutors and fetches while fitting the flash-heavy posture the deck already wants.",
    "Whitemane Lion": "An efficient instant-speed way to trigger Alela on opponents' turns while reusing ETB creatures like Spellstutter Sprite, Sower of Temptation, or Faerie Harbinger.",
    "Stonecloaker": "Similar to Whitemane Lion, but with built-in graveyard interaction. It is flexible disruption that also rebuys your ETB creatures.",
    "Mirror Entity": "The deck makes many small evasive bodies. Mirror Entity converts a modest Faerie board into a real finisher without asking for extra tribal setup.",
    "Distant Melody": "One of your strongest payoff draws. Naming Faerie after Alela has produced a few tokens can refill your hand dramatically.",
    "Maskwood Nexus": "This broadens all tribal synergies by turning your creatures and tokens into Faeries. It improves Spellstutter Sprite, Mistbind Clique, and any tribal card that counts Faeries.",
    "Faerie Tauntings": "Alela already wants you to pass with mana up and cast on opponents' turns. This makes that pattern drain the whole table while you keep interacting.",
    "Cloak and Dagger": "Alela produces Rogue tokens, so the auto-attach clause is very relevant. It helps push damage through while protecting key evasive attackers.",
    "Sword of Fire and Ice": "Excellent on evasive Faeries because they connect reliably. It adds card flow and removal while increasing the pressure from each token.",
    "Skullclamp": "Alela's 1/1 Faerie tokens naturally support Skullclamp. This gives the deck a steady way to turn spare tokens into real cards.",
    "Necromancy": "Flexible recursion that can be deployed at instant speed. It supports the reactive plan while rebuying high-impact creatures.",
    "Counterspell": "Cheap, unconditional interaction is one of the best ways to trigger Alela on opponents' turns while still advancing your board.",
    "Faerie Trickery": "A tribal-flavored counterspell that fits the deck's timing and flavor while adding exile utility.",
    "Sage's Dousing": "You are already playing many Wizards and Faeries, so this frequently functions as a counterspell plus card draw.",
    "Familiar's Ruse": "This turns your cheap utility creatures into value pieces. Bouncing Spellstutter Sprite or Faerie Harbinger is often upside, not a drawback.",
    "Peppersmoke": "Very on-theme removal. With a Faerie in play, it becomes efficient interaction plus a cantrip.",
    "Crib Swap": "Changeling matters here, so this doubles as tribal interaction while exiling problematic creatures.",
    "Nameless Inversion": "Another changeling tribal spell that keeps tribal synergies live while acting as efficient removal.",
    "Mortify": "Versatile interaction that answers both creatures and enchantments while fitting the hold-up plan.",
    "Brainstorm": "Cheap card selection is especially useful in a reactive deck that wants to leave mana open and spend it efficiently if nothing must be answered.",
    "Think Twice": "Instant-speed card draw is exactly what Alela wants. It lets you trigger on opponents' turns without needing a target.",
    "Thieves' Fortune": "The deck attacks with small evasive Rogues and Faeries, so prowl is realistic and the selection helps keep reactive hands flowing.",
    "Syphon Mind": "A strong multiplayer refill that also pressures opposing hands, complementing your evasive chip-damage plan.",
    "Dauthi Voidwalker": "Efficient pressure, graveyard disruption, and a threatening value ceiling all in one slot. It is not tribal, but it fits the tempo-disruption identity very well.",
    "Thunderclap Wyvern": "Another flash anthem that lets your evasive board hit harder without forcing you to tap out in your main phase.",
    "Shriekmaw": "Interactive creature slot that can be looped with bounce or recursion and helps keep the board clear for your flyers.",
    "Faerie Conclave": "A land that is also a Faerie matters more than it first appears. It supports tribal counts and gives you a threat without spending a card slot.",
    "Mutavault": "All creature types means it naturally supports your Faerie synergies and can turn on tribal counts at key moments.",
    "Urza's Saga": "Finds key utility artifacts like Skullclamp or Sol Ring while still functioning as a land slot.",
}


def derive_reason(card: dict) -> str:
    name = str(card.get("name", ""))
    if name in CUSTOM_REASON_LOOKUP:
        return CUSTOM_REASON_LOOKUP[name]

    category = str(card.get("category", ""))
    type_line = str(card.get("type_line", "") or "")
    oracle_text = str(card.get("oracle_text", "") or "").lower()
    tags = card.get("tags", [])
    color_identity = str(card.get("color_identity", "") or "")

    if category == "Lands":
        if name in {"Command Tower", "Exotic Orchard", "Reflecting Pool"}:
            return "This is premium fixing for an Esper Commander deck and helps you hold up interaction across multiple turns."
        if "faerie" in name.lower() or name == "Mutavault":
            return "This land does more than fix mana. It can also contribute to Faerie or tribal counts, which matters for cards like Spellstutter Sprite and Mistbind Clique."
        if "search your library" in oracle_text:
            return "This land smooths development and helps you hit the mana you need while keeping spell slots focused on flash interaction and tribal payoffs."
        if color_identity:
            return "This is part of the Esper mana base that keeps your colors stable so you can represent interaction on each opponent's turn."
        return "A stable mana slot that supports the reactive game plan by helping you consistently pass with options open."

    if category == "Artifacts / Enchantments":
        if "Ramp" in tags:
            return "This accelerates your mana so you can deploy Alela and still keep interaction available, which is important for a tempo-oriented Commander shell."
        if "Draw" in tags:
            return "This turns your small evasive creatures or spare tokens into sustained card flow, which helps reactive decks avoid running out of gas."
        if "Anthem" in tags or "Tokens" in tags:
            return "This pushes your token plan from incidental value into a real win condition by making your board wider, stronger, or more threatening."
        return "This supports the deck's broader tribal-tempo plan by improving efficiency, resilience, or combat pressure."

    if "Counter" in tags:
        return "This is exactly the kind of cheap interaction Alela wants. It lets you spend mana on opponents' turns, trigger token production, and stay ahead on tempo."
    if "Removal" in tags and "Draw" in tags:
        return "Flexible interaction with card flow is excellent here because it keeps your shields up without falling behind on resources."
    if "Removal" in tags:
        return "The deck wins through evasive combat, so efficient removal is important for clearing blockers and stopping the scariest opposing threats."
    if "Bounce" in tags:
        return "Bounce effects play well in a tempo shell and can also rebuy your own enter-the-battlefield creatures for extra value."
    if "Draw" in tags:
        return "This helps the deck keep cards flowing while you play reactively and avoid overcommitting to the board."
    if "Flash" in tags and "Faerie" in tags:
        return "A flash Faerie is ideal here because it advances tribal count, triggers Alela's preferred play pattern, and keeps your options open until the last moment."
    if "Flash" in tags:
        return "Flash fits the commander's game plan by letting you stay reactive and still commit to the board on opponents' turns."
    if "Faerie" in tags or "Rogue" in tags:
        return "This advances the tribal core, improves your Faerie count for payoffs, and helps your evasive combat plan matter more often."

    return "This was selected as a support piece for the overall Esper Faerie tempo plan, helping with efficiency, interaction, or closing pressure."


def derive_synergy(card: dict, deck_card_names: set[str]) -> dict:
    name = str(card.get("name", ""))
    if name in CUSTOM_SYNERGY_LOOKUP:
        related = [card_name for card_name in CUSTOM_SYNERGY_LOOKUP[name]["related"] if card_name in deck_card_names]
        return {
            "summary": CUSTOM_SYNERGY_LOOKUP[name]["summary"],
            "related": related,
        }

    tags = list(card.get("tags", []))
    category = str(card.get("category", ""))
    related: list[str] = []
    summary_parts: list[str] = []

    if "Faerie" in tags:
        related.extend(["Alela, Cunning Conqueror", "Spellstutter Sprite", "Mistbind Clique"])
        summary_parts.append("It contributes directly to the Faerie count for your tribal payoffs.")
    if "Flash" in tags:
        related.extend(["Alela, Cunning Conqueror", "Dreamspoiler Witches", "Faerie Tauntings"])
        summary_parts.append("Flash keeps it aligned with the deck's hold-up mana plan.")
    if "Counter" in tags:
        related.extend(["Alela, Cunning Conqueror", "Spellstutter Sprite", "Voracious Tome-Skimmer"])
        summary_parts.append("As cheap interaction, it is a strong way to trigger Alela while protecting your board.")
    if "Bounce" in tags:
        related.extend(["Spellstutter Sprite", "Faerie Harbinger", "Sower of Temptation"])
        summary_parts.append("Bounce and replay patterns help you loop useful enter-the-battlefield creatures.")
    if "Draw" in tags:
        related.extend(["Alela, Cunning Conqueror", "Skullclamp", "Distant Melody"])
        summary_parts.append("Card flow matters because the deck often plays at instant speed and trades resources incrementally.")
    if "Anthem" in tags:
        related.extend(["Alela, Cunning Conqueror", "Mirror Entity", "Cover of Darkness"])
        summary_parts.append("Anthem effects turn your small evasive board into a serious closing threat.")
    if category == "Lands":
        related.extend(["Alela, Cunning Conqueror", "Counterspell", "Mortify"])
        summary_parts.append("Its main role is to keep the mana stable enough to represent interaction across the table.")

    deduped_related: list[str] = []
    for card_name in related:
        if card_name in deck_card_names and card_name != name and card_name not in deduped_related:
            deduped_related.append(card_name)

    summary = " ".join(summary_parts).strip()
    if not summary:
        summary = "This card supports the deck's broader tempo and tribal structure even if it is not one of the headline synergy pieces."

    return {
        "summary": summary,
        "related": deduped_related[:5],
    }


def load_collection_lookup(collection_path: str) -> dict[str, dict]:
    df = read_csv_file(collection_path)
    ensure_columns(
        df,
        [
            "Name",
            "Scryfall ID",
            "type_line",
            "oracle_text",
            "mana_cost",
            "color_identity",
        ],
    )

    quantity_series = pd.to_numeric(df.get("Quantity"), errors="coerce").fillna(0).astype(int)
    df = df.assign(Quantity=quantity_series)
    lookup: dict[str, dict] = {}

    for _, row in df.sort_values(["Quantity", "Name"], ascending=[False, True]).iterrows():
        name = str(row["Name"]).strip()
        if not name or name in lookup:
            continue

        card_id = str(row.get("Scryfall ID", "")).strip()
        image_url = ""
        if card_id and card_id.lower() != "nan" and len(card_id) >= 2:
            image_url = build_scryfall_image_url(card_id)

        lookup[name] = {
            "name": name,
            "mana_cost": "" if pd.isna(row.get("mana_cost")) else str(row.get("mana_cost")),
            "type_line": "" if pd.isna(row.get("type_line")) else str(row.get("type_line")),
            "oracle_text": "" if pd.isna(row.get("oracle_text")) else str(row.get("oracle_text")),
            "color_identity": "" if pd.isna(row.get("color_identity")) else str(row.get("color_identity")),
            "scryfall_url": build_scryfall_page_url(row) or build_scryfall_search_url(name),
            "cardmarket_url": build_cardmarket_search_url(name),
            "image_url": image_url,
        }

    return lookup


def build_deck_cards(deck_path: str, collection_lookup: dict[str, dict]) -> tuple[str, list[dict], dict]:
    deck = json.loads(Path(deck_path).read_text(encoding="utf-8"))
    deck_name = deck["name"]
    cards: list[dict] = []
    refinement = deck.get("refinement", {})

    commander = dict(deck["commander"])
    commander.setdefault("category", "Commander")
    commander.setdefault("count", 1)
    commander.setdefault("mana_cost", "")
    commander.setdefault("type_line", "Legendary Creature")
    commander.setdefault("oracle_text", "")
    commander.setdefault("color_identity", "")
    commander.setdefault("image_url", "")
    commander.setdefault("cardmarket_url", build_cardmarket_search_url(commander["name"]))
    commander.setdefault("scryfall_url", build_scryfall_search_url(commander["name"]))
    commander["tags"] = derive_tags(commander)
    commander["reason"] = derive_reason(commander)
    cards.append(commander)

    for card in deck["cards"]:
        name = card["name"]
        if name not in collection_lookup:
            raise ValueError(f"Card not found in collection CSV: {name}")

        merged = dict(collection_lookup[name])
        merged["category"] = card["category"]
        merged["count"] = int(card.get("count", 1))
        merged["tags"] = derive_tags(merged)
        merged["mana_value"] = parse_mana_value(merged.get("mana_cost", ""))
        merged["reason"] = derive_reason(merged)
        cards.append(merged)

    commander["mana_value"] = parse_mana_value(commander.get("mana_cost", ""))
    commander["mana_source_colors"] = []

    deck_card_names = {card["name"] for card in cards}
    for card in cards:
        card["colors"] = split_color_identity(str(card.get("color_identity", "") or ""))
        card["mana_source_colors"] = derive_mana_source_colors(card)
        synergy = derive_synergy(card, deck_card_names)
        card["synergy_summary"] = synergy["summary"]
        card["related_cards"] = synergy["related"]

    commander_colors = set(commander["colors"])
    illegal_cards = []
    for card in cards[1:]:
        card_colors = set(card.get("colors", []))
        if not card_colors.issubset(commander_colors):
            illegal_cards.append(
                {
                    "name": card["name"],
                    "color_identity": ", ".join(card.get("colors", [])) or "Colorless",
                }
            )

    refinement["legality_warnings"] = illegal_cards

    return deck_name, cards, refinement


def render_html(deck_name: str, cards: list[dict], refinement: dict) -> str:
    cards_json = json.dumps(cards)
    refinement_json = json.dumps(refinement)
    title = html.escape(deck_name)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f3efe7;
      --panel: rgba(255, 251, 245, 0.92);
      --ink: #1d2430;
      --muted: #5a6678;
      --accent: #176087;
      --accent-soft: #d8ebf4;
      --border: rgba(29, 36, 48, 0.12);
      --shadow: 0 18px 48px rgba(24, 39, 56, 0.12);
      --radius: 18px;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: Georgia, "Palatino Linotype", serif;
      background:
        radial-gradient(circle at top left, rgba(41, 110, 145, 0.18), transparent 28%),
        radial-gradient(circle at right, rgba(39, 58, 92, 0.16), transparent 22%),
        linear-gradient(180deg, #f8f5ef 0%, #efe7d8 100%);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(360px, 1.1fr) minmax(320px, 0.9fr);
      gap: 24px;
      min-height: 100vh;
      padding: 24px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .left-panel {{
      padding: 24px;
    }}
    .right-panel {{
      position: sticky;
      top: 24px;
      align-self: start;
      padding: 18px;
      max-height: calc(100vh - 48px);
      overflow: auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 0.98;
    }}
    .subhead {{
      margin: 0 0 22px;
      color: var(--muted);
      font-size: 1rem;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto auto;
      gap: 12px;
      margin-bottom: 22px;
    }}
    input, select, button {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 10px 14px;
      font: inherit;
      background: white;
      color: var(--ink);
    }}
    button {{
      cursor: pointer;
      background: var(--accent);
      color: white;
      border-color: transparent;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
      gap: 10px;
      margin-bottom: 20px;
    }}
    .pill {{
      padding: 8px 12px;
      border-radius: 16px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.95rem;
      min-height: 60px;
    }}
    .pill strong {{
      display: block;
      font-size: 1.2rem;
      color: var(--ink);
      margin-bottom: 4px;
    }}
    .dashboard {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 16px;
      margin-bottom: 22px;
    }}
    .dashboard-secondary {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 22px;
    }}
    .mini-panel {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.72);
      padding: 14px;
    }}
    .mini-panel h3 {{
      margin: 0 0 10px;
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .curve-grid {{
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 8px;
      align-items: end;
      min-height: 144px;
    }}
    .curve-col {{
      display: grid;
      gap: 6px;
      justify-items: center;
    }}
    .curve-bar-wrap {{
      height: 104px;
      width: 100%;
      display: flex;
      align-items: end;
    }}
    .curve-bar {{
      width: 100%;
      border-radius: 10px 10px 4px 4px;
      background: linear-gradient(180deg, #76abc8 0%, #176087 100%);
      min-height: 8px;
    }}
    .curve-label, .curve-count {{
      font-size: 0.78rem;
      color: var(--muted);
    }}
    .role-grid, .breakdown-grid {{
      display: grid;
      gap: 8px;
    }}
    .color-grid {{
      display: grid;
      gap: 10px;
    }}
    .color-chip-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}
    .color-chip {{
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(23, 96, 135, 0.08);
      color: var(--ink);
      font-size: 0.9rem;
    }}
    .color-chip strong {{
      color: var(--accent);
    }}
    .role-row, .breakdown-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      font-size: 0.92rem;
    }}
    .bar-track {{
      grid-column: 1 / -1;
      width: 100%;
      height: 8px;
      background: rgba(23, 96, 135, 0.12);
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: var(--accent);
      border-radius: 999px;
    }}
    .section {{
      margin-top: 24px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 1.15rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    .card-list {{
      display: grid;
      gap: 8px;
    }}
    .card-row {{
      width: 100%;
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      border: 1px solid transparent;
      border-radius: 14px;
      padding: 10px 12px;
      text-align: left;
      background: rgba(255, 255, 255, 0.72);
      color: var(--ink);
      transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    }}
    .card-row:hover {{
      transform: translateY(-1px);
      border-color: var(--accent);
      background: white;
    }}
    .card-row.active {{
      border-color: var(--accent);
      background: white;
      box-shadow: 0 8px 18px rgba(23, 96, 135, 0.14);
    }}
    .card-row.related-highlight {{
      border-color: #7c9fb5;
      background: #f6fbff;
      box-shadow: inset 0 0 0 1px rgba(23, 96, 135, 0.08);
    }}
    .card-row.dimmed {{
      opacity: 0.42;
    }}
    .count {{
      font-weight: 700;
      color: var(--accent);
      text-align: center;
    }}
    .name-block {{
      min-width: 0;
    }}
    .name {{
      display: block;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.92rem;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .tag-row {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 5px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: #eef4f8;
      color: var(--accent);
      font-size: 0.76rem;
      line-height: 1.1;
    }}
    .mana {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .detail-image {{
      width: min(100%, 320px);
      border-radius: 18px;
      overflow: hidden;
      background: linear-gradient(180deg, #d4d9df, #b8c1cd);
      aspect-ratio: 63 / 88;
      display: grid;
      place-items: center;
      margin-bottom: 16px;
      margin-left: auto;
      margin-right: auto;
      border: 1px solid var(--border);
    }}
    .detail-image img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .detail-image.empty {{
      padding: 20px;
      color: var(--muted);
      text-align: center;
    }}
    .detail-head {{
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 16px;
      margin-bottom: 8px;
    }}
    .detail-head h3 {{
      margin: 0;
      font-size: 1.5rem;
    }}
    .detail-type, .detail-text, .detail-extra {{
      color: var(--muted);
    }}
    .detail-text {{
      white-space: pre-wrap;
      line-height: 1.45;
      margin: 16px 0;
      min-height: 4em;
    }}
    .detail-links {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .detail-tag-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
      margin-bottom: 8px;
    }}
    .detail-links a {{
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--ink);
      background: white;
    }}
    .empty-state {{
      color: var(--muted);
      padding: 16px 4px;
    }}
    .reason-box {{
      margin-top: 14px;
      padding: 14px;
      background: rgba(23, 96, 135, 0.08);
      border: 1px solid rgba(23, 96, 135, 0.12);
      border-radius: 14px;
    }}
    .reason-box h4 {{
      margin: 0 0 8px;
      font-size: 0.92rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--accent);
    }}
    .synergy-box {{
      margin-top: 14px;
      padding: 14px;
      background: rgba(124, 159, 181, 0.1);
      border: 1px solid rgba(124, 159, 181, 0.18);
      border-radius: 14px;
    }}
    .synergy-box h4 {{
      margin: 0 0 8px;
      font-size: 0.92rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #32566c;
    }}
    .compare-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-top: 10px;
    }}
    .compare-card {{
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255,255,255,0.72);
      padding: 14px;
    }}
    .compare-card h4 {{
      margin: 0 0 10px;
      font-size: 0.92rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--accent);
    }}
    .compare-header {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .compare-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .compare-links a, .compare-links button {{
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid rgba(23, 96, 135, 0.16);
      background: white;
      color: var(--ink);
      cursor: pointer;
      text-decoration: none;
      font: inherit;
    }}
    .compare-reason {{
      margin-top: 14px;
      padding: 14px;
      border-radius: 14px;
      background: rgba(23, 96, 135, 0.08);
      border: 1px solid rgba(23, 96, 135, 0.12);
    }}
    .synergy-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .synergy-link {{
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid rgba(23, 96, 135, 0.16);
      background: white;
      color: var(--ink);
      cursor: pointer;
    }}
    .upgrade-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 6px 0 8px;
    }}
    .upgrade-card-link {{
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid rgba(23, 96, 135, 0.16);
      background: white;
      color: var(--ink);
      cursor: pointer;
    }}
    .refinement-panel {{
      margin-top: 18px;
      border-top: 1px solid var(--border);
      padding-top: 16px;
    }}
    .refinement-group + .refinement-group {{
      margin-top: 16px;
    }}
    .refinement-group h4 {{
      margin: 0 0 10px;
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .refinement-item + .refinement-item {{
      margin-top: 10px;
    }}
    .refinement-item strong {{
      display: block;
      margin-bottom: 4px;
    }}
    @media (max-width: 980px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .right-panel {{
        position: static;
        max-height: none;
      }}
      .toolbar {{
        grid-template-columns: 1fr;
      }}
      .dashboard {{
        grid-template-columns: 1fr;
      }}
      .dashboard-secondary {{
        grid-template-columns: 1fr;
      }}
      .compare-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <section class="panel left-panel">
      <h1>{title}</h1>
      <p class="subhead">Local interactive deck browser. Click any card to inspect it, then jump to Scryfall if you want the full page.</p>

      <div class="stats" id="stats"></div>
      <div class="dashboard">
        <section class="mini-panel">
          <h3>Mana Curve</h3>
          <div id="mana-curve"></div>
        </section>
        <section class="mini-panel">
          <h3>Role And Type Breakdown</h3>
          <div id="role-counts"></div>
          <div style="height: 12px;"></div>
          <div id="type-breakdown"></div>
        </section>
      </div>
      <div class="dashboard-secondary">
        <section class="mini-panel">
          <h3>Color And Manabase Overview</h3>
          <div id="color-overview"></div>
        </section>
        <section class="mini-panel">
          <h3>Upgrade Paths</h3>
          <div id="upgrade-paths"></div>
        </section>
      </div>

      <div class="toolbar">
        <input id="search" type="search" placeholder="Search cards, types, rules text">
        <select id="category-filter">
          <option value="All">All categories</option>
        </select>
        <button id="reset-filters" type="button">Reset</button>
      </div>

      <div id="sections"></div>
    </section>

    <aside class="panel right-panel">
      <div id="detail"></div>
    </aside>
  </div>

  <script>
    const cards = {cards_json};
    const refinement = {refinement_json};
    const sectionsEl = document.getElementById('sections');
    const detailEl = document.getElementById('detail');
    const statsEl = document.getElementById('stats');
    const manaCurveEl = document.getElementById('mana-curve');
    const roleCountsEl = document.getElementById('role-counts');
    const typeBreakdownEl = document.getElementById('type-breakdown');
    const colorOverviewEl = document.getElementById('color-overview');
    const upgradePathsEl = document.getElementById('upgrade-paths');
    const searchEl = document.getElementById('search');
    const categoryFilterEl = document.getElementById('category-filter');
    const resetFiltersEl = document.getElementById('reset-filters');
    const remoteCardCache = new Map();

    let activeName = cards[0]?.name || '';
    let activeComparison = null;

    function categoryOrder(category) {{
      const order = ['Commander', 'Creatures', 'Artifacts / Enchantments', 'Instants / Sorceries', 'Lands'];
      const index = order.indexOf(category);
      return index === -1 ? 999 : index;
    }}

    function escapeHtml(value) {{
      return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
    }}

    function buildScryfallSearchUrl(name) {{
      return `https://scryfall.com/search?q=${{encodeURIComponent(`!"${{name}}"`)}}`;
    }}

    function buildCardmarketSearchUrl(name) {{
      return `https://www.cardmarket.com/en/Magic/Products/Search?searchString=${{encodeURIComponent(name)}}`;
    }}

    function mergeRemoteCardData(card, payload) {{
      card.image_url = card.image_url || payload.image_url || '';
      card.scryfall_url = card.scryfall_url || payload.scryfall_url || buildScryfallSearchUrl(card.name);
      card.cardmarket_url = card.cardmarket_url || payload.cardmarket_url || buildCardmarketSearchUrl(card.name);
      card.mana_cost = card.mana_cost || payload.mana_cost || '';
      card.type_line = card.type_line || payload.type_line || '';
      card.oracle_text = card.oracle_text || payload.oracle_text || '';
      if ((!card.color_identity || !String(card.color_identity).trim()) && payload.color_identity) {{
        card.color_identity = payload.color_identity;
      }}
      if ((!card.colors || !card.colors.length) && Array.isArray(payload.colors)) {{
        card.colors = payload.colors;
      }}
    }}

    function matchesFilter(card, search, category) {{
      if (category !== 'All' && card.category !== category) {{
        return false;
      }}

      if (!search) {{
        return true;
      }}

      const haystack = [
        card.name,
        card.type_line,
        card.oracle_text,
        card.mana_cost,
        card.category
      ].join('\\n').toLowerCase();

      return haystack.includes(search);
    }}

    function buildStats(visibleCards) {{
      const totalCards = visibleCards.reduce((sum, card) => sum + (card.count || 1), 0);
      const totalNonlands = visibleCards
        .filter((card) => card.category !== 'Lands')
        .reduce((sum, card) => sum + (card.count || 1), 0);
      const totalLands = visibleCards
        .filter((card) => card.category === 'Lands')
        .reduce((sum, card) => sum + (card.count || 1), 0);
      const faeries = visibleCards
        .filter((card) => (card.tags || []).includes('Faerie'))
        .reduce((sum, card) => sum + (card.count || 1), 0);
      const flashCards = visibleCards
        .filter((card) => (card.tags || []).includes('Flash'))
        .reduce((sum, card) => sum + (card.count || 1), 0);

      statsEl.innerHTML = `
        <span class="pill"><strong>${{totalCards}}</strong>Cards shown</span>
        <span class="pill"><strong>${{totalNonlands}}</strong>Nonlands</span>
        <span class="pill"><strong>${{totalLands}}</strong>Lands</span>
        <span class="pill"><strong>${{faeries}}</strong>Faerie cards</span>
        <span class="pill"><strong>${{flashCards}}</strong>Flash cards</span>
      `;
    }}

    function renderManaCurve(sourceCards) {{
      const buckets = new Map([
        ['0', 0], ['1', 0], ['2', 0], ['3', 0], ['4', 0], ['5', 0], ['6', 0], ['7+', 0]
      ]);

      sourceCards
        .filter((card) => card.category !== 'Lands')
        .forEach((card) => {{
          const value = Number(card.mana_value || 0);
          const key = value >= 7 ? '7+' : String(value);
          buckets.set(key, (buckets.get(key) || 0) + (card.count || 1));
        }});

      const maxCount = Math.max(...buckets.values(), 1);
      manaCurveEl.innerHTML = `
        <div class="curve-grid">
          ${{Array.from(buckets.entries()).map(([label, count]) => {{
            const height = Math.max(8, Math.round((count / maxCount) * 104));
            return `
              <div class="curve-col">
                <div class="curve-count">${{count}}</div>
                <div class="curve-bar-wrap"><div class="curve-bar" style="height:${{height}}px"></div></div>
                <div class="curve-label">${{label}}</div>
              </div>
            `;
          }}).join('')}}
        </div>
      `;
    }}

    function renderBreakdowns(sourceCards) {{
      const roleNames = ['Ramp', 'Draw', 'Removal', 'Counter', 'Bounce', 'Flash', 'Anthem', 'Tokens'];
      const roleCounts = roleNames.map((role) => {{
        const count = sourceCards
          .filter((card) => (card.tags || []).includes(role))
          .reduce((sum, card) => sum + (card.count || 1), 0);
        return [role, count];
      }}).filter(([, count]) => count > 0);

      const maxRole = Math.max(...roleCounts.map(([, count]) => count), 1);
      roleCountsEl.innerHTML = `
        <div class="role-grid">
          ${{roleCounts.map(([role, count]) => `
            <div class="role-row">
              <span>${{escapeHtml(role)}}</span>
              <span>${{count}}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${{Math.max(8, Math.round((count / maxRole) * 100))}}%"></div></div>
            </div>
          `).join('')}}
        </div>
      `;

      const typeCounts = [
        ['Creatures', sourceCards.filter((card) => card.category === 'Creatures').reduce((sum, card) => sum + (card.count || 1), 0)],
        ['Artifacts / Enchantments', sourceCards.filter((card) => card.category === 'Artifacts / Enchantments').reduce((sum, card) => sum + (card.count || 1), 0)],
        ['Instants / Sorceries', sourceCards.filter((card) => card.category === 'Instants / Sorceries').reduce((sum, card) => sum + (card.count || 1), 0)],
        ['Lands', sourceCards.filter((card) => card.category === 'Lands').reduce((sum, card) => sum + (card.count || 1), 0)],
      ];
      const maxType = Math.max(...typeCounts.map(([, count]) => count), 1);
      typeBreakdownEl.innerHTML = `
        <div class="breakdown-grid">
          ${{typeCounts.map(([label, count]) => `
            <div class="breakdown-row">
              <span>${{escapeHtml(label)}}</span>
              <span>${{count}}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${{Math.max(8, Math.round((count / maxType) * 100))}}%"></div></div>
            </div>
          `).join('')}}
        </div>
      `;
    }}

    function renderColorOverview(sourceCards) {{
      const COLOR_LABELS = {{ W: 'White', U: 'Blue', B: 'Black', R: 'Red', G: 'Green' }};
      const commander = sourceCards.find((card) => card.category === 'Commander');
      const deckColors = commander?.colors || [];
      const spellCards = sourceCards.filter((card) => card.category !== 'Lands');
      const colorCounts = new Map([['W', 0], ['U', 0], ['B', 0], ['R', 0], ['G', 0]]);
      const pipCounts = new Map([['W', 0], ['U', 0], ['B', 0], ['R', 0], ['G', 0]]);
      const landSources = new Map([['W', 0], ['U', 0], ['B', 0], ['R', 0], ['G', 0]]);

      spellCards.forEach((card) => {{
        (card.colors || []).forEach((color) => {{
          colorCounts.set(color, (colorCounts.get(color) || 0) + (card.count || 1));
        }});

        const manaCost = String(card.mana_cost || '');
        ['W', 'U', 'B', 'R', 'G'].forEach((color) => {{
          const matches = manaCost.match(new RegExp(`\\\\{{${{color}}(?:\\\\/[WUBRG])?\\\\}}`, 'g'));
          if (matches) {{
            pipCounts.set(color, (pipCounts.get(color) || 0) + matches.length * (card.count || 1));
          }}
        }});
      }});

      sourceCards.filter((card) => card.category === 'Lands').forEach((card) => {{
        (card.mana_source_colors || []).forEach((color) => {{
          landSources.set(color, (landSources.get(color) || 0) + (card.count || 1));
        }});
      }});

      const activeDeckColors = deckColors.map((color) => COLOR_LABELS[color] || color).join(', ') || 'Colorless';
      const totalDeckColors = deckColors.length;
      const barMax = Math.max(...['W', 'U', 'B', 'R', 'G'].map((color) => landSources.get(color) || 0), 1);

      colorOverviewEl.innerHTML = `
        <div class="color-grid">
          <div class="color-chip-row">
            <span class="color-chip"><strong>${{totalDeckColors}}</strong> deck colors</span>
            <span class="color-chip"><strong>${{escapeHtml(activeDeckColors)}}</strong></span>
          </div>
          <div class="breakdown-grid">
            ${{['W', 'U', 'B', 'R', 'G'].map((color) => `
              <div class="breakdown-row">
                <span>${{escapeHtml(COLOR_LABELS[color])}}: ${{colorCounts.get(color) || 0}} cards | ${{pipCounts.get(color) || 0}} pips | ${{landSources.get(color) || 0}} sources</span>
                <span>${{landSources.get(color) || 0}}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${{Math.max(0, Math.round(((landSources.get(color) || 0) / barMax) * 100))}}%"></div></div>
              </div>
            `).join('')}}
          </div>
        </div>
      `;
    }}

    function renderUpgradePaths() {{
      const upgradeSuggestions = Array.isArray(refinement.upgrade_suggestions) ? refinement.upgrade_suggestions : [];
      if (!upgradeSuggestions.length) {{
        upgradePathsEl.innerHTML = '<div class="meta">No upgrade suggestions stored for this deck yet.</div>';
        return;
      }}

      upgradePathsEl.innerHTML = `
        <div class="refinement-group">
          ${{upgradeSuggestions.map((item) => `
            <div class="refinement-item">
              <strong>${{escapeHtml(item.cut)}} -> ${{escapeHtml(item.add)}}</strong>
              <div class="upgrade-links">
                <button class="upgrade-card-link" type="button" data-upgrade-cut="${{escapeHtml(item.cut)}}" data-upgrade-add="${{escapeHtml(item.add)}}">Compare cards</button>
              </div>
              <div class="meta">${{escapeHtml(item.reason)}}</div>
            </div>
          `).join('')}}
        </div>
      `;

      upgradePathsEl.querySelectorAll('[data-upgrade-cut]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const suggestion = upgradeSuggestions.find((item) =>
            item.cut === button.dataset.upgradeCut && item.add === button.dataset.upgradeAdd
          ) || null;
          if (!suggestion) {{
            return;
          }}
          activeComparison = buildUpgradeComparison(suggestion);
          renderComparison(activeComparison);
        }});
      }});
    }}

    function buildUpgradeComparison(suggestion) {{
      return {{
        id: `${{suggestion.cut}} -> ${{suggestion.add}}`,
        reason: suggestion.reason,
        cutCard: cards.find((card) => card.name === suggestion.cut) || buildUpgradePreview(suggestion.cut, 'cut', suggestion),
        addCard: cards.find((card) => card.name === suggestion.add) || buildUpgradePreview(suggestion.add, 'add', suggestion),
      }};
    }}

    function buildUpgradePreview(name, mode, suggestion) {{
      const existing = cards.find((card) => card.name === name);
      if (existing) {{
        return existing;
      }}

      const relatedCards = [];
      if (suggestion?.cut && suggestion.cut !== name) {{
        relatedCards.push(suggestion.cut);
      }}
      if (suggestion?.add && suggestion.add !== name) {{
        relatedCards.push(suggestion.add);
      }}

      const upgradeReason = suggestion?.reason || (mode === 'add'
        ? 'Suggested as a higher-power or more thematic option for this slot.'
        : 'Current card in the deck that this suggestion would replace.');

      return {{
        name,
        count: 1,
        category: mode === 'add' ? 'Upgrade Suggestion' : 'Current Card',
        mana_cost: '',
        type_line: mode === 'add' ? 'Suggested Upgrade' : 'Current Deck Card',
        oracle_text: '',
        color_identity: '',
        image_url: '',
        scryfall_url: buildScryfallSearchUrl(name),
        cardmarket_url: buildCardmarketSearchUrl(name),
        tags: [mode === 'add' ? 'Upgrade' : 'Cut Candidate'],
        reason: upgradeReason,
        synergy_summary: mode === 'add'
          ? `Upgrade rationale: ${{upgradeReason}}`
          : `Current slot context: ${{upgradeReason}}`,
        related_cards: relatedCards,
        colors: [],
        mana_source_colors: [],
      }};
    }}

    function buildCardDetailMarkup(card) {{
      const imageBlock = card.image_url
        ? `<div class="detail-image"><img src="${{escapeHtml(card.image_url)}}" alt="${{escapeHtml(card.name)}}" loading="lazy"></div>`
        : '<div class="detail-image empty">Image unavailable in local data.<br>Use the Scryfall link below.</div>';

      const links = [];
      if (card.scryfall_url) {{
        links.push(`<a href="${{escapeHtml(card.scryfall_url)}}" target="_blank" rel="noreferrer">Open on Scryfall</a>`);
      }}
      if (card.cardmarket_url) {{
        links.push(`<a href="${{escapeHtml(card.cardmarket_url)}}" target="_blank" rel="noreferrer">Open on Cardmarket</a>`);
      }}
      if (card.image_url) {{
        links.push(`<a href="${{escapeHtml(card.image_url)}}" target="_blank" rel="noreferrer">Open image</a>`);
      }}
      const tagHtml = (card.tags || []).map((tag) => `<span class="tag">${{escapeHtml(tag)}}</span>`).join('');
      const synergyButtons = (card.related_cards || []).map((name) => `
        <button class="synergy-link" type="button" data-related-name="${{escapeHtml(name)}}">${{escapeHtml(name)}}</button>
      `).join('');

      return `
        ${{imageBlock}}
        <div class="detail-head">
          <div>
            <h3>${{escapeHtml(card.name)}}</h3>
            <div class="detail-type">${{escapeHtml(card.type_line || card.category)}}</div>
          </div>
          <div class="mana">${{escapeHtml(card.mana_cost || '')}}</div>
        </div>
        <div class="detail-extra">Category: ${{escapeHtml(card.category)}}${{card.count > 1 ? ` | Count: ${{card.count}}` : ''}}</div>
        <div class="detail-extra">${{escapeHtml(card.color_identity ? 'Color identity: ' + card.color_identity : '')}}</div>
        <div class="detail-tag-row">${{tagHtml}}</div>
        <div class="detail-text">${{escapeHtml(card.oracle_text || 'No oracle text stored for this entry.')}}</div>
        <div class="detail-links">${{links.join('')}}</div>
        <div class="reason-box">
          <h4>Why It Fits</h4>
          <div class="meta">${{escapeHtml(card.reason || "Selected to support the deck's Faerie tempo plan.")}}</div>
        </div>
        <div class="synergy-box">
          <h4>Combo And Synergy Links</h4>
          <div class="meta">${{escapeHtml(card.synergy_summary || "This card supports the deck's broader network of tribal and tempo synergies.")}}</div>
          <div class="synergy-links">${{synergyButtons || '<span class="meta">No explicit linked cards stored for this entry.</span>'}}</div>
        </div>
      `;
    }}

    function bindDetailInteractions(card) {{
      detailEl.querySelectorAll('[data-related-name]').forEach((button) => {{
        button.addEventListener('click', () => {{
          activeComparison = null;
          activeName = button.dataset.relatedName;
          renderList();
        }});
        button.addEventListener('mouseenter', () => {{
          highlightRelatedCards([button.dataset.relatedName]);
        }});
        button.addEventListener('mouseleave', clearRelatedHighlight);
      }});

      if (!card.image_url || !card.cardmarket_url || card.category === 'Commander' || !card.scryfall_url) {{
        hydrateCardData(card);
      }}
    }}

    function renderRefinementPanel() {{
      const sections = [];
      const maybeboard = Array.isArray(refinement.maybeboard) ? refinement.maybeboard : [];
      const cutCandidates = Array.isArray(refinement.cut_candidates) ? refinement.cut_candidates : [];
      const upgradeSuggestions = Array.isArray(refinement.upgrade_suggestions) ? refinement.upgrade_suggestions : [];
      const legalityWarnings = Array.isArray(refinement.legality_warnings) ? refinement.legality_warnings : [];

      if (legalityWarnings.length) {{
        sections.push(`
          <div class="refinement-group">
            <h4>Legality Warnings</h4>
            ${{legalityWarnings.map((item) => `
              <div class="refinement-item">
                <strong>${{escapeHtml(item.name)}}</strong>
                <div class="meta">Color identity: ${{escapeHtml(item.color_identity)}}. This card is outside the commander's allowed colors.</div>
              </div>
            `).join('')}}
          </div>
        `);
      }}

      if (maybeboard.length) {{
        sections.push(`
          <div class="refinement-group">
            <h4>Deck Anchors</h4>
            ${{maybeboard.map((item) => `
              <div class="refinement-item">
                <strong>${{escapeHtml(item.name)}}</strong>
                <div class="meta">${{escapeHtml(item.reason)}}</div>
              </div>
            `).join('')}}
          </div>
        `);
      }}

      if (cutCandidates.length) {{
        sections.push(`
          <div class="refinement-group">
            <h4>Possible Future Cuts</h4>
            ${{cutCandidates.map((item) => `
              <div class="refinement-item">
                <strong>${{escapeHtml(item.name)}}</strong>
                <div class="meta">${{escapeHtml(item.reason)}}</div>
              </div>
            `).join('')}}
          </div>
        `);
      }}

      if (upgradeSuggestions.length) {{
        sections.push(`
          <div class="refinement-group">
            <h4>Upgrade Paths</h4>
            ${{upgradeSuggestions.map((item) => `
              <div class="refinement-item">
                <strong>${{escapeHtml(item.cut)}} -> ${{escapeHtml(item.add)}}</strong>
                <div class="meta">${{escapeHtml(item.reason)}}</div>
              </div>
            `).join('')}}
          </div>
        `);
      }}

      return sections.length
        ? `<div class="refinement-panel">${{sections.join('')}}</div>`
        : '';
    }}

    function renderDetail(card) {{
      if (!card) {{
        detailEl.innerHTML = '<div class="empty-state">No card selected.</div>';
        return;
      }}

      detailEl.innerHTML = `
        ${{buildCardDetailMarkup(card)}}
        ${{card.category === 'Commander' ? renderRefinementPanel() : ''}}
      `;
      bindDetailInteractions(card);
    }}

    function renderComparison(comparison) {{
      if (!comparison) {{
        renderDetail(cards.find((card) => card.name === activeName) || cards[0]);
        return;
      }}

      detailEl.innerHTML = `
        <div class="compare-reason">
          <h4>Upgrade Comparison</h4>
          <div class="meta">${{escapeHtml(comparison.reason)}}</div>
        </div>
        <div class="compare-grid">
          <section class="compare-card" data-compare-slot="cut">
            <h4>Current Card</h4>
            ${{buildCardDetailMarkup(comparison.cutCard)}}
          </section>
          <section class="compare-card" data-compare-slot="add">
            <h4>Suggested Upgrade</h4>
            ${{buildCardDetailMarkup(comparison.addCard)}}
          </section>
        </div>
      `;

      detailEl.querySelectorAll('[data-related-name]').forEach((button) => {{
        button.addEventListener('click', () => {{
          activeComparison = null;
          activeName = button.dataset.relatedName;
          renderList();
        }});
        button.addEventListener('mouseenter', () => {{
          highlightRelatedCards([button.dataset.relatedName]);
        }});
        button.addEventListener('mouseleave', clearRelatedHighlight);
      }});

      const cutInspect = detailEl.querySelector('[data-compare-slot="cut"]');
      const addInspect = detailEl.querySelector('[data-compare-slot="add"]');
      if (cutInspect) {{
        if (!comparison.cutCard.image_url || !comparison.cutCard.cardmarket_url || !comparison.cutCard.scryfall_url) {{
          hydrateCardData(comparison.cutCard);
        }}
      }}
      if (addInspect) {{
        if (!comparison.addCard.image_url || !comparison.addCard.cardmarket_url || !comparison.addCard.scryfall_url) {{
          hydrateCardData(comparison.addCard);
        }}
      }}
    }}

    async function hydrateCardData(card) {{
      if (!card?.name) {{
        return;
      }}

      const cached = remoteCardCache.get(card.name);
      if (cached?.status === 'ready') {{
        mergeRemoteCardData(card, cached.payload);
        if (activeComparison && (activeComparison.cutCard.name === card.name || activeComparison.addCard.name === card.name)) {{
          renderComparison(activeComparison);
        }} else if (card.name === activeName) {{
          renderDetail(card);
        }}
        return;
      }}
      if (cached?.status === 'loading') {{
        return;
      }}

      remoteCardCache.set(card.name, {{ status: 'loading' }});

      try {{
        let response = await fetch(`https://api.scryfall.com/cards/named?exact=${{encodeURIComponent(card.name)}}`);
        if (!response.ok) {{
          response = await fetch(`https://api.scryfall.com/cards/named?fuzzy=${{encodeURIComponent(card.name)}}`);
        }}
        if (!response.ok) {{
          return;
        }}

        const payload = await response.json();
        const remotePayload = {{
          image_url: payload.image_uris?.normal || payload.card_faces?.[0]?.image_uris?.normal || '',
          scryfall_url: payload.scryfall_uri || buildScryfallSearchUrl(card.name),
          cardmarket_url: payload.purchase_uris?.cardmarket || buildCardmarketSearchUrl(card.name),
          mana_cost: payload.mana_cost || '',
          type_line: payload.type_line || '',
          oracle_text: payload.oracle_text || payload.card_faces?.[0]?.oracle_text || '',
          color_identity: Array.isArray(payload.color_identity) ? payload.color_identity.join(', ') : '',
          colors: Array.isArray(payload.color_identity) ? payload.color_identity : [],
        }};
        remoteCardCache.set(card.name, {{ status: 'ready', payload: remotePayload }});
        mergeRemoteCardData(card, remotePayload);

        if (activeComparison && (activeComparison.cutCard.name === card.name || activeComparison.addCard.name === card.name)) {{
          renderComparison(activeComparison);
        }} else if (card.name === activeName) {{
          renderDetail(card);
        }}
      }} catch (_error) {{
        const fallbackPayload = {{
          image_url: '',
          scryfall_url: card.scryfall_url || buildScryfallSearchUrl(card.name),
          cardmarket_url: card.cardmarket_url || buildCardmarketSearchUrl(card.name),
          mana_cost: card.mana_cost || '',
          type_line: card.type_line || '',
          oracle_text: card.oracle_text || '',
          color_identity: card.color_identity || '',
          colors: Array.isArray(card.colors) ? card.colors : [],
        }};
        remoteCardCache.set(card.name, {{ status: 'ready', payload: fallbackPayload }});
        mergeRemoteCardData(card, fallbackPayload);
        if (activeComparison && (activeComparison.cutCard.name === card.name || activeComparison.addCard.name === card.name)) {{
          renderComparison(activeComparison);
        }}
        // Keep the local viewer usable even if remote card hydration fails.
      }}
    }}

    function renderList() {{
      const search = searchEl.value.trim().toLowerCase();
      const category = categoryFilterEl.value;
      const visibleCards = cards.filter((card) => matchesFilter(card, search, category));
      buildStats(visibleCards);
      renderManaCurve(cards);
      renderBreakdowns(cards);
      renderColorOverview(cards);
      renderUpgradePaths();

      const grouped = new Map();
      visibleCards
        .sort((a, b) => categoryOrder(a.category) - categoryOrder(b.category) || a.name.localeCompare(b.name))
        .forEach((card) => {{
          if (!grouped.has(card.category)) {{
            grouped.set(card.category, []);
          }}
          grouped.get(card.category).push(card);
        }});

      if (!visibleCards.some((card) => card.name === activeName)) {{
        activeName = visibleCards[0]?.name || '';
      }}

      if (grouped.size === 0) {{
        sectionsEl.innerHTML = '<div class="empty-state">No cards match the current filters.</div>';
        renderDetail(null);
        return;
      }}

      sectionsEl.innerHTML = Array.from(grouped.entries()).map(([categoryName, categoryCards]) => `
        <section class="section">
          <div class="section-head">
            <h2>${{escapeHtml(categoryName)}}</h2>
            <span class="meta">${{categoryCards.reduce((sum, card) => sum + (card.count || 1), 0)}} cards</span>
          </div>
          <div class="card-list">
            ${{categoryCards.map((card) => `
              <button class="card-row ${{card.name === activeName ? 'active' : ''}}" type="button" data-name="${{escapeHtml(card.name)}}" title="${{escapeHtml(card.related_cards?.length ? 'Related: ' + card.related_cards.join(', ') : card.synergy_summary || '')}}">
                <span class="count">${{card.count || 1}}x</span>
                <span class="name-block">
                  <span class="name">${{escapeHtml(card.name)}}</span>
                  <span class="meta">${{escapeHtml(card.type_line || '')}}</span>
                  <span class="tag-row">${{(card.tags || []).map((tag) => `<span class="tag">${{escapeHtml(tag)}}</span>`).join('')}}</span>
                </span>
                <span class="mana">${{escapeHtml(card.mana_cost || '')}}</span>
              </button>
            `).join('')}}
          </div>
        </section>
      `).join('');

      document.querySelectorAll('.card-row').forEach((button) => {{
        button.addEventListener('click', () => {{
          activeComparison = null;
          activeName = button.dataset.name;
          renderList();
        }});
        button.addEventListener('mouseenter', () => {{
          const card = cards.find((entry) => entry.name === button.dataset.name);
          highlightRelatedCards(card?.related_cards || []);
        }});
        button.addEventListener('mouseleave', clearRelatedHighlight);
      }});

      if (activeComparison) {{
        renderComparison(activeComparison);
      }} else {{
        renderDetail(visibleCards.find((card) => card.name === activeName) || visibleCards[0]);
      }}
    }}

    function populateCategoryFilter() {{
      const categories = Array.from(new Set(cards.map((card) => card.category)))
        .sort((a, b) => categoryOrder(a) - categoryOrder(b));

      categories.forEach((category) => {{
        const option = document.createElement('option');
        option.value = category;
        option.textContent = category;
        categoryFilterEl.appendChild(option);
      }});
    }}

    function highlightRelatedCards(names) {{
      const relatedSet = new Set(names || []);
      const buttons = Array.from(document.querySelectorAll('.card-row'));
      if (!relatedSet.size) {{
        clearRelatedHighlight();
        return;
      }}

      buttons.forEach((button) => {{
        const isRelated = relatedSet.has(button.dataset.name);
        button.classList.toggle('related-highlight', isRelated);
        button.classList.toggle('dimmed', !isRelated && !button.classList.contains('active'));
      }});
    }}

    function clearRelatedHighlight() {{
      document.querySelectorAll('.card-row').forEach((button) => {{
        button.classList.remove('related-highlight');
        button.classList.remove('dimmed');
      }});
    }}

    searchEl.addEventListener('input', renderList);
    categoryFilterEl.addEventListener('change', renderList);
    resetFiltersEl.addEventListener('click', () => {{
      searchEl.value = '';
      categoryFilterEl.value = 'All';
      renderList();
    }});

    populateCategoryFilter();
    renderList();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    collection_lookup = load_collection_lookup(args.collection)
    deck_name, cards, refinement = build_deck_cards(args.deck, collection_lookup)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(deck_name, cards, refinement), encoding="utf-8")
    print(f"Saved deck viewer to: {output_path}")


if __name__ == "__main__":
    main()
