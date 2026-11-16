#!/usr/bin/env python3
"""Reverse-engineered dark fantasy data tables.

These tables are local approximations of dark fantasy game data (items,
skills, monsters, areas, affixes, etc.) used to drive the procedural
dark fantasy game generator. All values are original, local-only
approximations — no external game files are read or distributed.

Pure Python standard library.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Character classes
# ---------------------------------------------------------------------------

CLASS_DATA = {
    "amazon": {
        "name": "Amazon",
        "description": "Master of the bow and javelin, swift and precise.",
        "base_stats": {"strength": 20, "dexterity": 25, "vitality": 20, "energy": 15},
        "life_per_level": 2.0,
        "mana_per_level": 1.0,
        "stamina_per_level": 10.0,
        "skill_tree": {
            "bow": ["Inner Sight", "Slow Missiles", "Jab", "Critical Strike", "Double Throw",
                    "Potion Use", "Puncture", "Slow Missiles", "Critical Strike", "Multiple Shot",
                    "Dodge", "Inner Sight", "Power Strike", "Pierce", "Avoid", "Plague Javelin",
                    "Immolation Arrow", "Freezing Arrow", "Slow Missiles", "Critical Strike", "Multiple Shot",
                    "Dodge", "Inner Sight", "Power Strike", "Pierce", "Avoid", "Plague Javelin",
                    "Immolation Arrow", "Freezing Arrow", "Valkyrie", "Guided Arrow", "Charged Strike",
                    "Fend", "Lightning Strike", "Strafe", "Fury", "Penetrate"],
            "javelin_spear": ["Jab", "Power Strike", "Charged Strike", "Fend", "Lightning Strike",
                             "Fury", "Penetrate"],
            "passive_magic": ["Dodge", "Avoid", "Penetrate", "Inner Sight", "Slow Missiles",
                             "Critical Strike", "Multiple Shot", "Pierce", "Guided Arrow"],
        },
    },
    "sorceress": {
        "name": "Sorceress",
        "description": "Wielder of elemental fire, cold, and lightning.",
        "base_stats": {"strength": 15, "dexterity": 20, "vitality": 20, "energy": 25},
        "life_per_level": 1.2,
        "mana_per_level": 1.8,
        "stamina_per_level": 10.0,
        "skill_tree": {
            "fire": ["Fire Bolt", "Warmth", "Inferno", "Blaze", "Fire Ball", "Fire Wall",
                     "Enchant", "Meteor", "Fire Mastery", "Hydra"],
            "cold": ["Ice Bolt", "Frozen Armor", "Frost Nova", "Glacial Spike", "Ice Blast",
                     "Blizzard", "Cold Mastery", "Chilling Armor", "Frozen Orb"],
            "lightning": ["Charged Bolt", "Static Field", "Telekinesis", "Nova", "Lightning",
                          "Lightning Bolt", "Chain Lightning", "Thunder Storm", "Lightning Mastery"],
        },
    },
    "necromancer": {
        "name": "Necromancer",
        "description": "Commander of the dead and master of poison and bone.",
        "base_stats": {"strength": 20, "dexterity": 20, "vitality": 20, "energy": 20},
        "life_per_level": 1.6,
        "mana_per_level": 1.6,
        "stamina_per_level": 10.0,
        "skill_tree": {
            "summoning": ["Raise Skeleton", "Skeleton Mastery", "Raise Skeletal Mage", "Golem Mastery",
                         "Clay Golem", "Blood Golem", "Iron Golem", "Summon Resist", "Revive"],
            "poison": ["Poison Dagger", "Poison Explosion", "Bone Armor", "Teeth", "Bone Wall",
                      "Poison Nova", "Bone Prison", "Bone Spear"],
            "bone": ["Raise Skeleton", "Corpse Explosion", "Clay Golem", "Bone Armor", "Teeth",
                    "Bone Wall", "Poison Nova", "Bone Prison", "Bone Spear"],
        },
    },
    "paladin": {
        "name": "Paladin",
        "description": "Holy warrior wielding auras and righteous combat.",
        "base_stats": {"strength": 25, "dexterity": 20, "vitality": 25, "energy": 10},
        "life_per_level": 2.4,
        "mana_per_level": 1.0,
        "stamina_per_level": 10.0,
        "skill_tree": {
            "combat": ["Sacrifice", "Smite", "Might", "Holy Fire", "Holy Freeze", "Holy Shock",
                      "Concentration", "Blessed Hammer", "Vengeance", "Conversion"],
            "auras": ["Prayer", "Resist Fire", "Resist Cold", "Resist Lightning", "Defiance",
                     "Cleansing", "Meditation", "Redemption", "Vigor", "Salvation"],
            "offensive": ["Zeal", "Blessed Aim", "Fanaticism", "Conviction", "Holy Shield"],
        },
    },
    "barbarian": {
        "name": "Barbarian",
        "description": "Berserking melee warrior with warcries and combat mastery.",
        "base_stats": {"strength": 30, "dexterity": 20, "vitality": 25, "energy": 5},
        "life_per_level": 2.6,
        "mana_per_level": 0.8,
        "stamina_per_level": 12.0,
        "skill_tree": {
            "combat": ["Bash", "Stun", "Double Swing", "Concentrate", "Frenzy", "Berserk"],
            "masteries": ["Sword Mastery", "Axe Mastery", "Mace Mastery", "Polearm Mastery",
                         "Throwing Mastery", "Increased Stamina", "Natural Resistance"],
            "warcries": ["Howl", "Taunt", "Shout", "Battle Cry", "Battle Orders", "War Cry"],
        },
    },
    "druid": {
        "name": "Druid",
        "description": "Shape-shifter and summoner of the wilds.",
        "base_stats": {"strength": 20, "dexterity": 20, "vitality": 25, "energy": 15},
        "life_per_level": 2.0,
        "mana_per_level": 1.4,
        "stamina_per_level": 10.0,
        "skill_tree": {
            "summoning": ["Summon Spirit Wolf", "Summon Dire Wolf", "Summon Grizzly", "Heart of Wolverine",
                         "Oak Sage", "Vines", "Carrion Vine", "Solar Creeper", "Raven", "Summon Fenris"],
            "elemental": ["Fire Claws", "Feral Rage", "Maul", "Shapeshifting", "Werewolf",
                         "Lycanthropy", "Firestorm", "Molten Boulder", "Volcano", "Armageddon"],
            "shape_shifting": ["Werewolf", "Werebear", "Maul", "Ferocious Rage", "Fire Claws"],
        },
    },
    "assassin": {
        "name": "Assassin",
        "description": "Shadow warrior of martial arts and deadly traps.",
        "base_stats": {"strength": 20, "dexterity": 25, "vitality": 20, "energy": 15},
        "life_per_level": 2.0,
        "mana_per_level": 1.0,
        "stamina_per_level": 10.0,
        "skill_tree": {
            "martial_arts": ["Claw Mastery", "Psychic Hammer", "Tiger Strike", "Dragon Talon",
                            "Fists of Fire", "Dragon Tail", "Claw Mastery", "Tiger Strike",
                            "Dragon Claw", "Cobra Strike", "Fists of Fire", "Dragon Flight"],
            "traps": ["Fire Blast", "Blade Sentinel", "Charged Sentry", "Wake of Fire", "Wake of Destruction",
                     "Blade Fury", "Death Sentry", "Blade Sentinel", "Charged Sentry"],
            "shadow": ["Fade", "Psi Blade", "Weapon Block", "Cloak of Shadows", "Mind Blast",
                      "Shadow Warrior", "Shadow Master"],
        },
    },
}

# ---------------------------------------------------------------------------
# Base stats and derived formulas
# ---------------------------------------------------------------------------

STAT_ORDER = ["strength", "dexterity", "vitality", "energy"]

DAMAGE_TYPES = ["physical", "fire", "cold", "lightning", "poison", "magic"]

RESISTANCE_ORDER = ["fire_resist", "cold_resist", "lightning_resist", "poison_resist"]

MAX_RESISTANCE = 75


def compute_life(vitality: int, level: int, base_life: float, life_per_level: float) -> int:
    return int(base_life + vitality * 2.0 + life_per_level * (level - 1))


def compute_mana(energy: int, level: int, base_mana: float, mana_per_level: float) -> int:
    return int(base_mana + energy * 2.5 + mana_per_level * (level - 1))


def compute_stamina(level: int) -> int:
    return 100 + int(10 * level)


def compute_defense(dexterity: int, level: int, base_defense: int) -> int:
    return int(base_defense + dexterity + level)


def compute_chance_to_block(dexterity: int, level: int, shield_block: int) -> int:
    return max(0, min(75, int((dexterity * shield_block) / (level * 2 + 10))))


# ---------------------------------------------------------------------------
# Item base types
# ---------------------------------------------------------------------------

ITEM_BASES = {
    # Weapons
    "short_bow": {"type": "weapon", "weapon_type": "bow", "damage_min": 2, "damage_max": 5,
                  "speed": 8, "strength_req": 25, "dexterity_req": 25, "hands": 2, "class": "amazon"},
    "long_bow": {"type": "weapon", "weapon_type": "bow", "damage_min": 4, "damage_max": 9,
                 "speed": 10, "strength_req": 45, "dexterity_req": 55, "hands": 2, "class": "amazon"},
    "short_sword": {"type": "weapon", "weapon_type": "sword", "damage_min": 3, "damage_max": 6,
                    "speed": 5, "strength_req": 20, "dexterity_req": 25, "hands": 1, "class": None},
    "long_sword": {"type": "weapon", "weapon_type": "sword", "damage_min": 5, "damage_max": 10,
                   "speed": 6, "strength_req": 35, "dexterity_req": 40, "hands": 1, "class": None},
    "clubs": {"type": "weapon", "weapon_type": "club", "damage_min": 2, "damage_max": 7,
              "speed": 6, "strength_req": 30, "dexterity_req": 15, "hands": 1, "class": None},
    "dagger": {"type": "weapon", "weapon_type": "dagger", "damage_min": 2, "damage_max": 5,
               "speed": 4, "strength_req": 15, "dexterity_req": 20, "hands": 1, "class": None},
    "axe": {"type": "weapon", "weapon_type": "axe", "damage_min": 4, "damage_max": 8,
            "speed": 7, "strength_req": 40, "dexterity_req": 30, "hands": 1, "class": None},
    "spear": {"type": "weapon", "weapon_type": "spear", "damage_min": 3, "damage_max": 7,
              "speed": 7, "strength_req": 35, "dexterity_req": 35, "hands": 2, "class": None},
    # Armor
    "leather_armor": {"type": "armor", "armor_type": "body", "defense": 14, "strength_req": 15,
                      "durability": 24},
    "chain_mail": {"type": "armor", "armor_type": "body", "defense": 20, "strength_req": 45,
                   "durability": 28},
    "plate_mail": {"type": "armor", "armor_type": "body", "defense": 40, "strength_req": 75,
                   "durability": 36},
    "leather_cap": {"type": "armor", "armor_type": "helm", "defense": 4, "strength_req": 0,
                    "durability": 12},
    "skull_cap": {"type": "armor", "armor_type": "helm", "defense": 6, "strength_req": 0,
                  "durability": 14},
    "kite_shield": {"type": "armor", "armor_type": "shield", "defense": 22, "strength_req": 45,
                    "block_chance": 48, "durability": 40},
    "large_shield": {"type": "armor", "armor_type": "shield", "defense": 28, "strength_req": 75,
                     "block_chance": 56, "durability": 48},
    "leather_gloves": {"type": "armor", "armor_type": "gloves", "defense": 6, "strength_req": 0,
                       "durability": 16},
    "leather_boots": {"type": "armor", "armor_type": "boots", "defense": 7, "strength_req": 0,
                      "durability": 20},
    # Jewelry
    "ring": {"type": "jewelry", "slot": "ring", "strength_req": 0, "durability": 0},
    "amulet": {"type": "jewelry", "slot": "amulet", "strength_req": 0, "durability": 0},
}

# Equipment slots
EQUIPMENT_SLOTS = ["helm", "amulet", "body", "weapon_left", "weapon_right", "shield", "gloves",
                   "boots", "belt", "ring_left", "ring_right"]

# ---------------------------------------------------------------------------
# Item qualities
# ---------------------------------------------------------------------------

QUALITY_NAMES = {
    "inferior": "Low Quality",
    "normal": "Normal",
    "superior": "Superior",
    "magic": "Magic",
    "rare": "Rare",
    "set": "Set",
    "unique": "Unique",
    "crafted": "Crafted",
}

QUALITY_COLORS = {
    "inferior": "#8C7851",
    "normal": "#FFFFFF",
    "superior": "#00D000",
    "magic": "#1976D2",
    "rare": "#FFD700",
    "set": "#22B14C",
    "unique": "#C73C47",
    "crafted": "#7A3FF0",
}

# ---------------------------------------------------------------------------
# Affixes (prefixes / suffixes) - reverse engineered approximations
# ---------------------------------------------------------------------------

AFFIXES = {
    # Prefixes
    "prefix_strong": {"slot": "prefix", "level": 1, "strength": 5, "name": "Strong"},
    "prefix_mighty": {"slot": "prefix", "level": 6, "strength": 10, "name": "Mighty"},
    "prefix_quick": {"slot": "prefix", "level": 1, "dexterity": 5, "name": "Quick"},
    "prefix_fine": {"slot": "prefix", "level": 4, "dexterity": 10, "name": "Fine"},
    "prefix_healthy": {"slot": "prefix", "level": 2, "vitality": 5, "life": 20, "name": "Healthy"},
    "prefix_robust": {"slot": "prefix", "level": 8, "vitality": 10, "life": 40, "name": "Robust"},
    "prefix_wise": {"slot": "prefix", "level": 3, "energy": 5, "mana": 20, "name": "Wise"},
    "prefix_brilliant": {"slot": "prefix", "level": 9, "energy": 10, "mana": 40, "name": "Brilliant"},
    "prefix_fire": {"slot": "prefix", "level": 5, "fire_damage": "1-4", "fire_resist": 10,
                    "name": "Fiery"},
    "prefix_cold": {"slot": "prefix", "level": 5, "cold_damage": "1-4", "cold_resist": 10,
                    "name": "Icy"},
    "prefix_lightning": {"slot": "prefix", "level": 5, "lightning_damage": "1-4",
                         "lightning_resist": 10, "name": "Sparking"},
    "prefix_poison": {"slot": "prefix", "level": 5, "poison_damage": "1-4", "poison_resist": 10,
                      "name": "Venomous"},
    # Suffixes
    "s_prefix_of_strength": {"slot": "suffix", "level": 1, "strength": 3, "name": "of Strength"},
    "s_prefix_of_quickness": {"slot": "suffix", "level": 4, "dexterity": 3, "name": "of Quickness"},
    "s_prefix_of_health": {"slot": "suffix", "level": 2, "vitality": 3, "life": 15, "name": "of Health"},
    "s_prefix_of_mana": {"slot": "suffix", "level": 3, "energy": 3, "mana": 15, "name": "of Mana"},
    "s_prefix_of_fire_resist": {"slot": "suffix", "level": 4, "fire_resist": 15, "name": "of Fire Resistance"},
    "s_prefix_of_cold_resist": {"slot": "suffix", "level": 4, "cold_resist": 15, "name": "of Cold Resistance"},
    "s_prefix_of_lightning_resist": {"slot": "suffix", "level": 4, "lightning_resist": 15,
                                     "name": "of Lightning Resistance"},
    "s_prefix_of_poison_resist": {"slot": "suffix", "level": 4, "poison_resist": 15,
                                  "name": "of Poison Resistance"},
    "s_prefix_of_defense": {"slot": "suffix", "level": 1, "defense_percent": 10, "name": "of Defense"},
    "s_prefix_of_absorbing": {"slot": "suffix", "level": 8, "absorb_all": 5, "name": "of Absorbing"},
}

AFFIX_NAMES = [a["name"] for a in AFFIXES.values()]

# ---------------------------------------------------------------------------
# Unique items (reverse engineered approximations)
# ---------------------------------------------------------------------------

UNIQUE_ITEMS = {
    "unique_griffons": {"name": "Griffon's Eye", "base": "diadem", "type": "armor", "armor_type": "helm",
                        "level": 85, "stats": {"lightning_damage": "7-142", "lightning_resist": 10,
                                               "cast_speed": 20, "magic_find": 30},
                        "color": "#C73C47"},
    "unique_shako": {"name": "Harlequin Crest", "base": "circlet", "type": "armor", "armor_type": "helm",
                     "level": 80, "stats": {"all_skills": 2, "strength": 2, "dexterity": 2,
                                            "vitality": 2, "energy": 2, "life": 100, "mana": 100,
                                            "magic_find": 50}, "color": "#C73C47"},
    "unique_stone_of_jordan": {"name": "Stone of Jordan", "base": "ring", "type": "jewelry", "slot": "ring",
                               "level": 30, "stats": {"all_skills": 1, "mana": 25, "mana_regen": 25},
                               "color": "#C73C47"},
    "unique_windforce": {"name": "Windforce", "base": "hydra_bow", "type": "weapon", "weapon_type": "bow",
                         "damage_min": 40, "damage_max": 100, "level": 73,
                         "stats": {"knockback": True, "dexterity": 20, "life_leech": 8, "mana_leech": 6},
                         "color": "#C73C47"},
    "unique_tyraels": {"name": "Tyrael's Might", "base": "sacred_armor", "type": "armor", "armor_type": "body",
                       "level": 85, "stats": {"all_resist": 30, "defense_percent": 200, "indestructible": True},
                       "color": "#C73C47"},
}

# ---------------------------------------------------------------------------
# Sets (reverse engineered approximations)
# ---------------------------------------------------------------------------

ITEM_SETS = {
    "set_tal_rasha": {"name": "Tal Rasha's Wrappings", "pieces": 6,
                      "pieces_data": {
                          "tal_rasha_orb": {"name": "Tal Rasha's Lidless Eye", "base": "orb",
                                            "stats": {"all_skills": 1, "fire_resist": 25,
                                                      "lightning_resist": 25, "cold_resist": 25,
                                                      "poison_resist": 25}},
                          "tal_rasha_amulet": {"name": "Tal Rasha's Adjudication", "base": "amulet",
                                               "stats": {"all_skills": 1, "cold_resist": 25}},
                          "tal_rasha_mask": {"name": "Tal Rasha's Face", "base": "circlet",
                                             "stats": {"all_skills": 1, "fire_resist": 25}},
                          "tal_rasha_chest": {"name": "Tal Rasha's Guard", "base": "archon_plate",
                                              "stats": {"all_skills": 1, "all_resist": 30}},
                          "tal_rasha_belt": {"name": "Tal Rasha's Alloy", "base": "heavy_belt",
                                             "stats": {"all_skills": 1, "lightning_resist": 25}},
                          "tal_rasha_feet": {"name": "Tal Rasha's Feet", "base": "myrmidon_greaves",
                                             "stats": {"all_skills": 1, "poison_resist": 25}},
                      },
                      "set_bonuses": {2: {"cold_resist": 25}, 4: {"fire_resist": 25},
                                      6: {"all_skills": 3, "faster_cast_rate": 35}},
                      "color": "#22B14C"},
    "set_immortal_king": {"name": "Immortal King's", "pieces": 6,
                          "pieces_data": {
                              "ik_helm": {"name": "Immortal King's Soul Cage", "base": "great_helm",
                                          "stats": {"strength": 30, "life": 150, "all_resist": 20}},
                              "ik_armor": {"name": "Immortal King's Forge", "base": "giant_mail",
                                           "stats": {"strength": 20, "defense_percent": 120}},
                              "ik_belt": {"name": "Immortal King's Will", "base": "war_belt",
                                          "stats": {"strength": 20, "life": 100, "stamina": 50}},
                              "ik_gloves": {"name": "Immortal King's Detail", "base": "heavy_brawler",
                                            "stats": {"strength": 20, "attack_speed": 20}},
                              "ik_weapon": {"name": "Immortal King's Stoner", "base": "colossus_maul",
                                            "stats": {"strength": 40, "damage_percent": 200}},
                              "ik_boots": {"name": "Immortal King's Stride", "base": "war_boots",
                                           "stats": {"strength": 20, "run_walk": 20}},
                          },
                          "set_bonuses": {2: {"life": 200}, 4: {"strength": 30}, 6: {"all_resist": 40}},
                          "color": "#22B14C"},
}

# ---------------------------------------------------------------------------
# Monsters
# ---------------------------------------------------------------------------

MONSTER_FAMILIES = {
    "fallen": {"name": "Fallen", "base_stats": {"level": 2, "health": 20, "damage_min": 1, "damage_max": 4,
                                                "defense": 10, "experience": 4}, "color": "#E74C3C"},
    "carver": {"name": "Carver", "base_stats": {"level": 4, "health": 28, "damage_min": 3, "damage_max": 7,
                                                "defense": 14, "experience": 8}, "color": "#C0392B"},
    "soul_slasher": {"name": "Soul Slasher", "base_stats": {"level": 8, "health": 45, "damage_min": 6, "damage_max": 12,
                                                           "defense": 20, "experience": 16}, "color": "#A93226"},
    "goatman": {"name": "Goatman", "base_stats": {"level": 6, "health": 40, "damage_min": 5, "damage_max": 10,
                                                 "defense": 16, "experience": 12}, "color": "#8E44AD"},
    "skeleton": {"name": "Skeleton", "base_stats": {"level": 8, "health": 35, "damage_min": 6, "damage_max": 11,
                                                    "defense": 18, "experience": 14}, "color": "#BDC3C7"},
    "zombie": {"name": "Zombie", "base_stats": {"level": 5, "health": 55, "damage_min": 4, "damage_max": 9,
                                                "defense": 12, "experience": 10}, "color": "#7F8C8D"},
    "succubus": {"name": "Succubus", "base_stats": {"level": 12, "health": 60, "damage_min": 8, "damage_max": 15,
                                                   "defense": 24, "experience": 24}, "color": "#9B59B6"},
    "lacuni": {"name": "Lacuni", "base_stats": {"level": 14, "health": 70, "damage_min": 10, "damage_max": 18,
                                                "defense": 28, "experience": 28}, "color": "#E67E22"},
    "balrog": {"name": "Balrog", "base_stats": {"level": 20, "health": 150, "damage_min": 15, "damage_max": 28,
                                                "defense": 40, "experience": 60}, "color": "#34495E"},
}

ACT_BOSSES = {
    "andariel": {"name": "Andariel, Maiden of Anguish", "act": 1, "level": 16, "health": 800,
                 "damage_min": 12, "damage_max": 24, "defense": 60, "poison_damage": "5-10",
                 "experience": 5000, "color": "#C0392B"},
    "duriel": {"name": "Duriel, Lord of Pain", "act": 2, "level": 25, "health": 1500,
               "damage_min": 20, "damage_max": 38, "defense": 90, "cold_damage": "8-15",
               "experience": 12000, "color": "#2980B9"},
    "mephisto": {"name": "Mephisto, Lord of Hatred", "act": 3, "level": 40, "health": 3000,
                 "damage_min": 35, "damage_max": 60, "defense": 130, "lightning_damage": "10-20",
                 "experience": 40000, "color": "#8E44AD"},
    "diablo": {"name": "Diablo, Lord of Terror", "act": 4, "level": 50, "health": 5000,
               "damage_min": 50, "damage_max": 85, "defense": 170, "fire_damage": "15-25",
               "experience": 100000, "color": "#C73C47"},
    "baal": {"name": "Baal, Lord of Destruction", "act": 5, "level": 60, "health": 8000,
             "damage_min": 65, "damage_max": 110, "defense": 210, "magic_damage": "20-35",
             "experience": 250000, "color": "#C0392B"},
}

# ---------------------------------------------------------------------------
# Areas / Acts
# ---------------------------------------------------------------------------

AREAS = {
    "rogue_encampment": {"name": "Rogue Encampment", "act": 1, "type": "town", "tileset": "town_a1",
                         "safe": True, "has_waypoint": True, "npcs": ["akara", "charsi", "gheed", "kashya"]},
    "cold_plains": {"name": "Cold Plains", "act": 1, "type": "outdoor", "tileset": "plain_a1",
                    "safe": False, "has_waypoint": True, "monsters": ["fallen", "goatman"]},
    "stony_field": {"name": "Stony Field", "act": 1, "type": "outdoor", "tileset": "plain_a1",
                    "safe": False, "has_waypoint": True, "monsters": ["fallen", "carver"]},
    "burial_grounds": {"name": "Burial Grounds", "act": 1, "type": "dungeon", "tileset": "dungeon_a1",
                       "safe": False, "has_waypoint": True, "monsters": ["skeleton", "zombie"]},
    "catacombs_level_1": {"name": "The Catacombs, Level 1", "act": 1, "type": "dungeon", "tileset": "dungeon_a1",
                          "safe": False, "has_waypoint": False, "monsters": ["skeleton", "zombie", "succubus"]},
    "cathedral": {"name": "Cathedral", "act": 1, "type": "dungeon", "tileset": "dungeon_a1",
                  "safe": False, "has_waypoint": False, "monsters": ["succubus", "lacuni"],
                  "boss": "andariel"},
    "lutar_pass": {"name": "Lutar Pass", "act": 2, "type": "outdoor", "tileset": "desert_a2",
                   "safe": False, "has_waypoint": True},
    "dry_hills": {"name": "Dry Hills", "act": 2, "type": "outdoor", "tileset": "desert_a2",
                  "safe": False, "has_waypoint": True},
    "harem": {"name": "The Harem", "act": 2, "type": "dungeon", "tileset": "dungeon_a2",
              "safe": False, "has_waypoint": False, "boss": "duriel"},
    "travincal": {"name": "Travincal", "act": 3, "type": "outdoor", "tileset": "city_a3",
                  "safe": False, "has_waypoint": True},
    "temple_city": {"name": "Temple City", "act": 3, "type": "dungeon", "tileset": "dungeon_a3",
                    "safe": False, "has_waypoint": True, "boss": "mephisto"},
    "chaos_sanctuary": {"name": "Chaos Sanctuary", "act": 4, "type": "dungeon", "tileset": "hell_a4",
                        "safe": False, "has_waypoint": False, "boss": "diablo"},
    "worldstone_keep": {"name": "Worldstone Keep", "act": 5, "type": "dungeon", "tileset": "hell_a5",
                        "safe": False, "has_waypoint": True, "boss": "baal"},
}

ACTS = {
    1: {"name": "Act I: The Den of Evil", "town": "rogue_encampment", "color": "#3498DB"},
    2: {"name": "Act II: The Secret of the Vizjerei", "town": "lutar_pass", "color": "#F1C40F"},
    3: {"name": "Act III: The Blackened Temple", "town": "travincal", "color": "#2ECC71"},
    4: {"name": "Act IV: The Lord of Terror", "town": "chaos_sanctuary", "color": "#E74C3C"},
    5: {"name": "Act V: Lord of Destruction", "town": "worldstone_keep", "color": "#9B59B6"},
}

# ---------------------------------------------------------------------------
# Quest structure
# ---------------------------------------------------------------------------

QUESTS = {
    "act1": [
        {"id": "den_of_evil", "name": "Den of Evil", "act": 1,
         "description": "Clear the den of evil monsters near the Rogue Encampment.",
         "reward": "One socket added to a normal item, or +20 stat points."},
        {"id": "sisters_to_the_slaughter", "name": "Sisters to the Slaughter", "act": 1,
         "description": "Kill Andariel, Maiden of Anguish.",
         "reward": "Resistance to all elements."},
    ],
    "act2": [
        {"id": "radaments_ring", "name": "Radament's Lair", "act": 2,
         "description": "Enter Radament's lair and kill the mummy.",
         "reward": "Scroll of Resistance."},
    ],
    "act3": [
        {"id": "lam_esens_tome", "name": "Lam Esen's Tome", "act": 3,
         "description": "Find Lam Esen's Tome in the Temple of Light.",
         "reward": "Charsi's imbue quest reward."},
    ],
}

# ---------------------------------------------------------------------------
# NPCs
# ---------------------------------------------------------------------------

NPCDATA = {
    "akara": {"name": "Akara", "role": "Rogue Sister", "location": "rogue_encampment",
              "services": ["identify", "heal", "mercenaries"],
              "dialogue": "May the light guide you, hero. The darkness stirs in the monastery."},
    "charsi": {"name": "Charsi", "role": "Blacksmith", "location": "rogue_encampment",
               "services": ["repair", "imbue"],
               "dialogue": "I can repair your gear, or imbue a normal item with rare properties."},
    "gheed": {"name": "Gheed", "role": "Merchant", "location": "rogue_encampment",
              "services": ["gamble", "repair"],
              "dialogue": "Looking to gamble your gold away, eh? I might have just what you need..."},
    "kashya": {"name": "Kashya", "role": "Rogue Captain", "location": "rogue_encampment",
               "services": ["hire_mercenary"],
               "dialogue": "The rogues need help. Will you take up arms against the darkness?"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def roll_affix(quality: str, level: int) -> dict | None:
    """Pick a random affix appropriate for item quality and character level."""
    import random
    eligible = [a for a in AFFIXES.values() if a["level"] <= level]
    if not eligible:
        return None
    if quality in {"magic", "rare"}:
        return random.choice(eligible)
    return None


def generate_item_name(base_id: str, quality: str, prefix: str | None, suffix: str | None) -> str:
    base = ITEM_BASES.get(base_id, {})
    base_name = base_id.replace("_", " ").title()
    parts = []
    if prefix:
        parts.append(prefix["name"])
    parts.append(base_name)
    if suffix:
        parts.append(suffix["name"])
    return " ".join(parts)
