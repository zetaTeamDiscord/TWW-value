import discord
from discord import app_commands
import json
import os
import datetime
import asyncio
import platform
import psutil
import io
import sys
import warnings
import threading
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from collections import defaultdict

warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    TOKEN: str = "token"
    VALIDATION_CHANNEL_ID: int = 0
    VALIDATOR_ROLE_NAME: str = "Value Helper"
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    VALUES_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "values.json")
    LOG_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.json")
    WATCHES_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watches.json")
    PROFILES_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")
    LOCATE_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locate.json")
    SETTINGS_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
    STATISTICS_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statistics.json")
    ALERTS_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.json")
    FAVORITES_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorites.json")
    TRADES_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.json")
    POLLS_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polls.json")


config = Config()


class Colors:
    VERY_LOW  = 0xFF0000
    LOW       = 0xED4245
    MEDIUM    = 0xFEE75C
    HIGH      = 0x57F287
    VERY_HIGH = 0x2ECC71
    GOOD      = 0x57F287
    VERY_GOOD = 0x2ECC71
    BAD       = 0xED4245
    VERY_BAD  = 0xED4245
    DEFAULT   = 0x5865F2
    SUCCESS   = 0x57F287
    WARNING   = 0xFEE75C
    ERROR     = 0xED4245
    INFO      = 0x3498DB
    PURPLE    = 0x9B59B6
    ORANGE    = 0xE67E22

    @staticmethod
    def get(value: str) -> int:
        return {
            "Very Low":  Colors.VERY_LOW,
            "Low":       Colors.LOW,
            "Medium":    Colors.MEDIUM,
            "High":      Colors.HIGH,
            "Very High": Colors.VERY_HIGH,
            "Good":      Colors.GOOD,
            "Very Good": Colors.VERY_GOOD,
            "Bad":       Colors.BAD,
            "Very Bad":  Colors.VERY_BAD,
        }.get(value, Colors.DEFAULT)


class ANSI:
    RESET  = "\u001b[0m"
    BOLD   = "\u001b[1m"
    WHITE  = "\u001b[2;37m"
    GREEN  = "\u001b[2;32m"
    YELLOW = "\u001b[2;33m"
    BLUE   = "\u001b[2;34m"
    RED    = "\u001b[2;31m"
    PURPLE = "\u001b[2;35m"
    CYAN   = "\u001b[2;36m"

    VALUE_COLORS = {
        "Very Low":  "\u001b[2;31m",
        "Low":       "\u001b[2;31m",
        "Medium":    "\u001b[2;33m",
        "High":      "\u001b[2;32m",
        "Very High": "\u001b[2;32m",
        "Good":      "\u001b[2;34m",
        "Very Good": "\u001b[2;34m",
        "Bad":       "\u001b[2;31m",
        "Very Bad":  "\u001b[2;31m",
    }

    @staticmethod
    def colorize(label: str, value: str) -> str:
        color = ANSI.VALUE_COLORS.get(value, ANSI.WHITE)
        return f"{ANSI.WHITE}{ANSI.BOLD}{label}:{ANSI.RESET} {color}{value}{ANSI.RESET}"


DEMAND_CHOICES = [
    app_commands.Choice(name="Very Low",  value="Very Low"),
    app_commands.Choice(name="Low",       value="Low"),
    app_commands.Choice(name="Medium",    value="Medium"),
    app_commands.Choice(name="High",      value="High"),
    app_commands.Choice(name="Very High", value="Very High"),
]

STABILITY_CHOICES = [
    app_commands.Choice(name="Very Bad",  value="Very Bad"),
    app_commands.Choice(name="Bad",       value="Bad"),
    app_commands.Choice(name="Medium",    value="Medium"),
    app_commands.Choice(name="Good",      value="Good"),
    app_commands.Choice(name="Very Good", value="Very Good"),
]

OVERPAY_CHOICES = DEMAND_CHOICES

STABILITY_EMOJIS = {
    "Very Bad":  "🔴",
    "Bad":       "🔴",
    "Medium":    "🟡",
    "Good":      "🟢",
    "Very Good": "🟢",
}


def get_timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_log_entry(action: str, item: str, user, **kwargs) -> Dict:
    return {
        "date":      get_timestamp(),
        "action":    action,
        "item":      item,
        "user_name": str(user),
        "user_id":   getattr(user, "id", 0),
        **kwargs,
    }


class ValueParser:
    @staticmethod
    def parse(value_str: str) -> int:
        value_str = value_str.lower().replace(",", "").strip()
        try:
            if value_str.endswith("k"):
                return int(float(value_str[:-1]) * 1_000)
            elif value_str.endswith("m"):
                return int(float(value_str[:-1]) * 1_000_000)
            else:
                return int(float(value_str))
        except ValueError:
            raise ValueError("Invalid format. Use: 220k, 1.5M, 500000, etc.")

    @staticmethod
    def format(value: int) -> str:
        if value >= 1_000_000:
            f = f"{value / 1_000_000:.1f}M"
            return f.replace(".0M", "M")
        elif value >= 1_000:
            f = f"{value / 1_000:.1f}k"
            return f.replace(".0k", "k")
        return str(value)


def can_validate_suggestions(member: discord.Member) -> bool:
    if member.id == config.OWNER_ID:
        return True
    return any(r.name == config.VALIDATOR_ROLE_NAME for r in member.roles)


class DataManager:
    def __init__(self):
        self.values:           Dict[str, Any]        = {}
        self.pending_requests: Dict[int, Dict]       = {}
        self.active_polls:     Dict[int, Dict]       = {}
        self.watches:          Dict[str, List[int]]  = {}
        self.profiles:         Dict[int, Dict]       = {}
        self.chests:           List[Dict]            = []
        self.settings:         Dict[str, Any]        = {}
        self.statistics:       Dict[str, Any]        = {}
        self.alerts:           Dict[int, List[Dict]] = {}
        self.favorites:        Dict[int, List[str]]  = {}
        self.trades:           List[Dict]            = []
        self._logs_cache:      Optional[List[Dict]]  = None
        self._logs_dirty:      bool                  = True
        self.load_all_data()

    def load_all_data(self):
        self.load_values()
        self.load_watches()
        self.load_profiles()
        self.load_chests()
        self.load_settings()
        self.load_statistics()
        self.load_alerts()
        self.load_favorites()
        self.load_trades()
        self.load_active_polls()

    def load_values(self):
        try:
            with open(config.VALUES_PATH, "r", encoding="utf-8") as f:
                self.values = json.load(f)
            print(f"Loaded {len(self.values)} items")
        except FileNotFoundError:
            self.values = {}
            self.save_values()
        except json.JSONDecodeError:
            self.values = {}

    def save_values(self):
        with open(config.VALUES_PATH, "w", encoding="utf-8") as f:
            json.dump(self.values, f, indent=2, ensure_ascii=False)

    def load_watches(self):
        try:
            with open(config.WATCHES_PATH, "r", encoding="utf-8") as f:
                self.watches = json.load(f)
        except FileNotFoundError:
            self.watches = {}
            self.save_watches()
        except json.JSONDecodeError:
            self.watches = {}

    def save_watches(self):
        with open(config.WATCHES_PATH, "w", encoding="utf-8") as f:
            json.dump(self.watches, f, indent=2, ensure_ascii=False)

    def load_profiles(self):
        try:
            with open(config.PROFILES_PATH, "r", encoding="utf-8") as f:
                self.profiles = {int(k): v for k, v in json.load(f).items()}
        except FileNotFoundError:
            self.profiles = {}
            self.save_profiles()
        except json.JSONDecodeError:
            self.profiles = {}

    def save_profiles(self):
        with open(config.PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(self.profiles, f, indent=2, ensure_ascii=False)

    def load_chests(self):
        try:
            with open(config.LOCATE_PATH, "r", encoding="utf-8") as f:
                self.chests = json.load(f)
            print(f"Loaded {len(self.chests)} chest locations")
        except FileNotFoundError:
            self.chests = []
            self.save_chests()
        except json.JSONDecodeError:
            self.chests = []

    def save_chests(self):
        with open(config.LOCATE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.chests, f, indent=2, ensure_ascii=False)

    def load_settings(self):
        try:
            with open(config.SETTINGS_PATH, "r", encoding="utf-8") as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            self.settings = {
                "commands_enabled": {
                    "value": True, "list": True, "search": True,
                    "compare": True, "calculator": True, "history": True,
                    "watch": True, "unwatch": True, "profile": True,
                    "heatmap": True, "leaderboard": True, "createpoll": True,
                    "closepoll": True, "additem": True, "suggestmodify": True,
                    "locatechest": True, "locatechestlist": True,
                    "serverinfo": True, "botinfo": True, "statistics": True,
                    "addfavorite": True, "removefavorite": True,
                    "viewfavorites": True, "setalert": True,
                    "viewalerts": True, "removealert": True,
                    "logtrade": True, "tradehistory": True, "market": True,
                    "help": True, "adminadd": True, "edititem": True,
                    "deleteitem": True, "reload": True, "backup": True,
                    "loadbackup": True, "dashboard": True, "announce": True,
                    "togglecommand": True, "maintenance": True,
                    "banuser": True, "setvalue": True, "massdelete": True,
                    "exportjson": True, "clearhistory": True,
                    "userinfo": True, "resetprofile": True,
                    "broadcastdm": True, "itemstats": True,
                    "synccommands": True, "cleanwatches": True,
                    "setbotname": True, "addnote": True,
                    "pollstats": True, "serverinvite": True,
                    "importjson": True, "globalstats": True,
                },
                "maintenance_mode": False,
                "allowed_servers": [],
                "banned_users": [],
                "feature_flags": {
                    "trading_system":  True,
                    "market_analysis": True,
                    "price_alerts":    True,
                    "auto_backup":     True,
                },
            }
            self.save_settings()
        except json.JSONDecodeError:
            self.settings = {}

    def save_settings(self):
        with open(config.SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    def load_statistics(self):
        try:
            with open(config.STATISTICS_PATH, "r", encoding="utf-8") as f:
                self.statistics = json.load(f)
        except FileNotFoundError:
            self.statistics = {
                "total_commands_used": 0,
                "commands_breakdown":  {},
                "total_searches":      0,
                "total_polls_created": 0,
                "total_trades_logged": 0,
                "uptime_start":        get_timestamp(),
                "servers_joined":      0,
                "servers_left":        0,
            }
            self.save_statistics()
        except json.JSONDecodeError:
            self.statistics = {}

    def save_statistics(self):
        with open(config.STATISTICS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.statistics, f, indent=2, ensure_ascii=False)

    def load_alerts(self):
        try:
            with open(config.ALERTS_PATH, "r", encoding="utf-8") as f:
                self.alerts = {int(k): v for k, v in json.load(f).items()}
        except FileNotFoundError:
            self.alerts = {}
            self.save_alerts()
        except json.JSONDecodeError:
            self.alerts = {}

    def save_alerts(self):
        with open(config.ALERTS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.alerts, f, indent=2, ensure_ascii=False)

    def load_favorites(self):
        try:
            with open(config.FAVORITES_PATH, "r", encoding="utf-8") as f:
                self.favorites = {int(k): v for k, v in json.load(f).items()}
        except FileNotFoundError:
            self.favorites = {}
            self.save_favorites()
        except json.JSONDecodeError:
            self.favorites = {}

    def save_favorites(self):
        with open(config.FAVORITES_PATH, "w", encoding="utf-8") as f:
            json.dump(self.favorites, f, indent=2, ensure_ascii=False)

    def load_trades(self):
        try:
            with open(config.TRADES_PATH, "r", encoding="utf-8") as f:
                self.trades = json.load(f)
        except FileNotFoundError:
            self.trades = []
            self.save_trades()
        except json.JSONDecodeError:
            self.trades = []

    def save_trades(self):
        with open(config.TRADES_PATH, "w", encoding="utf-8") as f:
            json.dump(self.trades, f, indent=2, ensure_ascii=False)

    def load_active_polls(self):
        try:
            with open(config.POLLS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
                self.active_polls = {
                    int(k): {
                        **v,
                        "votes": {int(uid): val for uid, val in v.get("votes", {}).items()},
                    }
                    for k, v in raw.items()
                }
            print(f"Loaded {len(self.active_polls)} active poll(s)")
        except FileNotFoundError:
            self.active_polls = {}
            self.save_active_polls()
        except json.JSONDecodeError:
            self.active_polls = {}

    def save_active_polls(self):
        serializable = {
            str(k): {
                **v,
                "votes": {str(uid): val for uid, val in v.get("votes", {}).items()},
            }
            for k, v in self.active_polls.items()
        }
        with open(config.POLLS_PATH, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    def get_logs(self) -> List[Dict]:
        if self._logs_dirty or self._logs_cache is None:
            try:
                with open(config.LOG_PATH, "r", encoding="utf-8") as f:
                    self._logs_cache = json.load(f)
            except FileNotFoundError:
                self._logs_cache = []
            except json.JSONDecodeError:
                self._logs_cache = []
            self._logs_dirty = False
        return self._logs_cache

    def save_log(self, entry: Dict):
        logs = self.get_logs()
        logs.append(entry)
        with open(config.LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        self._logs_dirty = True

    def update_profile(self, user_id: int, action: str):
        if user_id not in self.profiles:
            self.profiles[user_id] = {
                "total_suggestions": 0, "accepted_suggestions": 0,
                "rejected_suggestions": 0, "poll_votes": 0,
                "watched_items": 0, "first_activity": get_timestamp(),
                "last_activity": get_timestamp(), "total_trades": 0,
                "successful_trades": 0, "commands_used": 0,
            }
        p = self.profiles[user_id]
        for field, val in {
            "commands_used": 0, "total_trades": 0, "successful_trades": 0,
            "total_suggestions": 0, "accepted_suggestions": 0,
            "rejected_suggestions": 0, "poll_votes": 0,
            "watched_items": 0, "first_activity": get_timestamp(),
        }.items():
            p.setdefault(field, val)
        p["last_activity"] = get_timestamp()
        action_map = {
            "suggestion":          "total_suggestions",
            "suggestion_accepted": "accepted_suggestions",
            "suggestion_rejected": "rejected_suggestions",
            "poll_vote":           "poll_votes",
            "trade":               "total_trades",
            "command":             "commands_used",
        }
        if action in action_map:
            p[action_map[action]] += 1
        self.save_profiles()

    def increment_command_usage(self, command_name: str):
        self.statistics["total_commands_used"] += 1
        self.statistics["commands_breakdown"].setdefault(command_name, 0)
        self.statistics["commands_breakdown"][command_name] += 1
        self.save_statistics()

    def is_command_enabled(self, command_name: str) -> bool:
        return self.settings.get("commands_enabled", {}).get(command_name, True)

    def toggle_command(self, command_name: str, enabled: bool):
        self.settings.setdefault("commands_enabled", {})[command_name] = enabled
        self.save_settings()


data_manager = DataManager()


async def item_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    def _val(t):
        try:
            return ValueParser.parse(t[1].get("value", "0"))
        except:
            return 0
    matches = sorted(
        [(n, d) for n, d in data_manager.values.items() if current.lower() in n.lower()],
        key=_val, reverse=True
    )
    return [app_commands.Choice(name=n[:100], value=n) for n, _ in matches[:25]]


async def poll_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=f"{p.get('item', '?')} (ID: {pid})"[:100], value=str(pid))
        for pid, p in data_manager.active_polls.items()
        if current.lower() in p.get("item", "").lower()
    ][:25]


async def chest_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=c.get("name", f"Chest #{i+1}")[:100], value=str(i))
        for i, c in enumerate(data_manager.chests)
        if current.lower() in c.get("name", "").lower()
    ][:25]


async def command_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    cmds = list(data_manager.settings.get("commands_enabled", {}).keys())
    return [app_commands.Choice(name=c, value=c) for c in cmds if current.lower() in c.lower()][:25]


def global_command_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if data_manager.settings.get("maintenance_mode", False):
            if interaction.user.id != config.OWNER_ID:
                await interaction.response.send_message(
                    "The bot is currently under maintenance. Please try again later.", ephemeral=True)
                return False
        if interaction.user.id in data_manager.settings.get("banned_users", []):
            await interaction.response.send_message("You are banned from using this bot.", ephemeral=True)
            return False
        cmd = interaction.command.name
        if not data_manager.is_command_enabled(cmd):
            await interaction.response.send_message(f"The command `/{cmd}` is currently disabled.", ephemeral=True)
            return False
        data_manager.increment_command_usage(cmd)
        data_manager.update_profile(interaction.user.id, "command")
        return True
    return app_commands.check(predicate)


def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("This command is restricted to the bot owner.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


class ValueModal(discord.ui.Modal, title="Propose a Value"):
    value_input = discord.ui.TextInput(
        label="Value (e.g. 220k, 1.2M)",
        placeholder="Enter your proposed value...",
        required=True,
        max_length=10
    )

    def __init__(self, poll_id: int):
        super().__init__()
        self.poll_id = poll_id

    async def on_submit(self, interaction: discord.Interaction):
        poll = data_manager.active_polls.get(self.poll_id)
        if not poll:
            return await interaction.response.send_message("This poll no longer exists.", ephemeral=True)
        try:
            value = ValueParser.parse(self.value_input.value)
        except ValueError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        old_vote = poll["votes"].get(interaction.user.id)
        if old_vote is not None:
            poll["counts"][old_vote] = poll["counts"].get(old_vote, 1) - 1
            if poll["counts"][old_vote] <= 0:
                poll["counts"].pop(old_vote, None)

        poll["votes"][interaction.user.id] = value
        poll["counts"][value] = poll["counts"].get(value, 0) + 1
        data_manager.save_active_polls()
        data_manager.update_profile(interaction.user.id, "poll_vote")
        await self._update_poll_message(interaction, poll)
        await interaction.response.send_message(
            f"Vote registered: **{ValueParser.format(value)}**", ephemeral=True)

    async def _update_poll_message(self, interaction, poll):
        try:
            message = await interaction.channel.fetch_message(self.poll_id)
        except discord.NotFound:
            return
        embed = message.embeds[0]
        total_votes = sum(poll["counts"].values())
        average = (
            sum(v * c for v, c in poll["counts"].items()) / total_votes
            if total_votes > 0 else 0
        )
        sorted_votes = sorted(poll["counts"].items(), key=lambda x: x[1], reverse=True)
        vote_details = "\n".join(
            f"• **{ValueParser.format(v)}** — {c} vote(s)" for v, c in sorted_votes
        )
        field_val = (
            f"Average: **{ValueParser.format(int(average))}**\n"
            f"{total_votes} vote(s)\n\n{vote_details}"
        )
        if len(embed.fields) > 1:
            embed.set_field_at(1, name="Current Votes", value=field_val, inline=False)
        else:
            embed.add_field(name="Current Votes", value=field_val, inline=False)
        await message.edit(embed=embed, view=PollView(self.poll_id))


class PollView(discord.ui.View):
    def __init__(self, poll_id: int):
        super().__init__(timeout=None)
        self.poll_id = poll_id

    @discord.ui.button(label="Propose a Value", style=discord.ButtonStyle.green, emoji="💰")
    async def vote_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ValueModal(self.poll_id))


class TradeModal(discord.ui.Modal, title="Log a Trade"):
    item_given = discord.ui.TextInput(
        label="Item(s) Given",
        placeholder="Items you gave, separated by commas",
        required=True,
        max_length=200
    )
    item_received = discord.ui.TextInput(
        label="Item(s) Received",
        placeholder="Items you received, separated by commas",
        required=True,
        max_length=200
    )
    partner = discord.ui.TextInput(
        label="Trade Partner (optional)",
        placeholder="Username or ID",
        required=False,
        max_length=50
    )
    notes = discord.ui.TextInput(
        label="Notes (optional)",
        placeholder="Any extra information",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        trade_data = {
            "user_id":        interaction.user.id,
            "user_name":      str(interaction.user),
            "items_given":    [i.strip() for i in self.item_given.value.split(",")],
            "items_received": [i.strip() for i in self.item_received.value.split(",")],
            "partner":        self.partner.value or "Unknown",
            "notes":          self.notes.value or "",
            "timestamp":      get_timestamp(),
        }
        data_manager.trades.append(trade_data)
        data_manager.save_trades()
        data_manager.update_profile(interaction.user.id, "trade")

        embed = discord.Embed(
            title="Trade Logged",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(
            name="You Gave",
            value="\n".join(f"• {i}" for i in trade_data["items_given"]),
            inline=True
        )
        embed.add_field(
            name="You Received",
            value="\n".join(f"• {i}" for i in trade_data["items_received"]),
            inline=True
        )
        if trade_data["partner"] != "Unknown":
            embed.add_field(name="Partner", value=trade_data["partner"], inline=False)
        if trade_data["notes"]:
            embed.add_field(name="Notes", value=trade_data["notes"], inline=False)
        embed.set_footer(text=f"Trade #{len(data_manager.trades)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ValueBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        for poll_id in data_manager.active_polls:
            self.add_view(PollView(poll_id))
        await self.tree.sync()
        print("Commands synchronized")

    async def on_ready(self):
        print(f"Connected as {self.user}")
        print(
            f"{len(data_manager.values)} items | "
            f"{len(data_manager.chests)} chests | "
            f"{len(self.tree.get_commands())} commands"
        )
        print("Console ready. Type 'help' for available commands.")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(data_manager.values)} items | /help"
        ))
        asyncio.get_event_loop().run_in_executor(None, console_handler)

    async def on_guild_join(self, guild: discord.Guild):
        data_manager.statistics["servers_joined"] += 1
        data_manager.save_statistics()
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="Thanks for adding me!",
                    description=(
                        "`/help` — All commands\n"
                        "`/value` — Check item values\n"
                        "`/serverinfo` — Server stats"
                    ),
                    color=Colors.SUCCESS
                )
                await ch.send(embed=embed)
                break

    async def on_guild_remove(self, guild: discord.Guild):
        data_manager.statistics["servers_left"] += 1
        data_manager.save_statistics()

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.user.id:
            return
        request = data_manager.pending_requests.pop(payload.message_id, None)
        if not request:
            return
        emoji = str(payload.emoji)
        if emoji not in ("✅", "❌"):
            data_manager.pending_requests[payload.message_id] = request
            return

        if request.get("channel_type") == "public":
            guild = self.get_guild(payload.guild_id)
            if not guild:
                data_manager.pending_requests[payload.message_id] = request
                return
            member = guild.get_member(payload.user_id)
            if not member or not can_validate_suggestions(member):
                data_manager.pending_requests[payload.message_id] = request
                try:
                    ch = self.get_channel(payload.channel_id)
                    if ch:
                        msg = await ch.fetch_message(payload.message_id)
                        await msg.remove_reaction(payload.emoji, member)
                except:
                    pass
                return
        else:
            if payload.user_id != config.OWNER_ID:
                data_manager.pending_requests[payload.message_id] = request
                return

        try:
            if request.get("channel_type") == "public":
                ch = self.get_channel(config.VALIDATION_CHANNEL_ID)
                msg = await ch.fetch_message(payload.message_id)
            else:
                owner = await self.fetch_user(config.OWNER_ID)
                dm = await owner.create_dm()
                msg = await dm.fetch_message(payload.message_id)
            embed = msg.embeds[0]
        except:
            return

        validator = self.get_user(payload.user_id)
        validator_name = str(validator) if validator else "Unknown"
        if emoji == "✅":
            await self.handle_approval(request, embed, msg, validator_name)
        elif emoji == "❌":
            await self.handle_rejection(request, embed, msg, validator_name)

    async def handle_approval(self, request, embed, message, validator_name="Owner"):
        item = request["item"]
        if request["type"] == "add":
            data_manager.values[item] = request["data"]
            action = "ADD ACCEPTED"
            notif = f"Your add request for **{item}** was accepted by **{validator_name}**."
        else:
            old_value = data_manager.values[item].get("value", "?")
            for k, v in request["data"].items():
                if v:
                    data_manager.values[item][k] = v
            new_value = data_manager.values[item].get("value", "?")
            action = "EDIT ACCEPTED"
            notif = f"Your suggestion for **{item}** was accepted by **{validator_name}**."
            if old_value != new_value and item in data_manager.watches:
                wn = discord.Embed(
                    title=f"{item} has been updated!",
                    description=f"**{old_value}** → **{new_value}**",
                    color=Colors.WARNING,
                    timestamp=datetime.datetime.now()
                )
                wn.set_footer(text="You are watching this item • /unwatch to stop")
                for uid in data_manager.watches[item]:
                    try:
                        u = await self.fetch_user(uid)
                        await u.send(f"<@{uid}>", embed=wn)
                    except:
                        pass

        data_manager.update_profile(request["user_id"], "suggestion_accepted")
        data_manager.save_values()
        data_manager.save_log({
            "date": get_timestamp(), "action": action, "item": item,
            "data": request["data"], "user_name": request["user_name"],
            "user_id": request["user_id"], "validator": validator_name
        })
        embed.color = Colors.SUCCESS
        embed.set_footer(text=f"Accepted by {validator_name} on {get_timestamp()}")
        await message.edit(embed=embed)
        await message.clear_reactions()
        try:
            u = await self.fetch_user(request["user_id"])
            await u.send(notif)
        except:
            pass

    async def handle_rejection(self, request, embed, message, validator_name="Owner"):
        action = "ADD REJECTED" if request["type"] == "add" else "EDIT REJECTED"
        notif = (
            f"Your add request for **{request['item']}** was rejected by **{validator_name}**."
            if request["type"] == "add"
            else f"Your suggestion for **{request['item']}** was rejected by **{validator_name}**."
        )
        data_manager.update_profile(request["user_id"], "suggestion_rejected")
        data_manager.save_log({
            "date": get_timestamp(), "action": action, "item": request["item"],
            "data": request["data"], "user_name": request["user_name"],
            "user_id": request["user_id"], "validator": validator_name
        })
        embed.color = Colors.ERROR
        embed.set_footer(text=f"Rejected by {validator_name} on {get_timestamp()}")
        await message.edit(embed=embed)
        await message.clear_reactions()
        try:
            u = await self.fetch_user(request["user_id"])
            await u.send(notif)
        except:
            pass


bot = ValueBot()


def console_handler():
    CONSOLE_HELP = """
Available console commands:
  status           - Bot status and statistics
  items            - List all items
  reload           - Reload all data files
  backup           - Create a backup of values.json
  maintenance on   - Enable maintenance mode
  maintenance off  - Disable maintenance mode
  announce <msg>   - Send an announcement to all servers
  servers          - List all servers the bot is in
  polls            - List active polls
  logs <n>         - Show last n logs (default: 10)
  clear            - Clear the console screen
  help             - Show this help message
  exit / quit      - Stop the bot
"""
    print(CONSOLE_HELP)

    while True:
        try:
            raw = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Shutting down...")
            asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
            break

        if not raw:
            continue

        parts = raw.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "status":
            proc = psutil.Process()
            mem = proc.memory_info().rss / 1024 / 1024
            print(
                f"\n  Bot:         {bot.user}\n"
                f"  Servers:     {len(bot.guilds)}\n"
                f"  Members:     {sum(g.member_count for g in bot.guilds):,}\n"
                f"  Items:       {len(data_manager.values)}\n"
                f"  Chests:      {len(data_manager.chests)}\n"
                f"  Active Polls:{len(data_manager.active_polls)}\n"
                f"  Trades:      {len(data_manager.trades)}\n"
                f"  Memory:      {mem:.1f} MB\n"
                f"  Maintenance: {'ON' if data_manager.settings.get('maintenance_mode') else 'OFF'}\n"
                f"  Commands:    {data_manager.statistics.get('total_commands_used', 0):,} used"
            )

        elif cmd == "items":
            if not data_manager.values:
                print("No items in the list.")
            else:
                print(f"\n{len(data_manager.values)} items:")
                for i, (name, d) in enumerate(list(data_manager.values.items())[:30], 1):
                    print(
                        f"  {i:02}. {name} — {d.get('value', '?')} | "
                        f"D:{d.get('demand', '?')} | S:{d.get('stability', '?')}"
                    )
                if len(data_manager.values) > 30:
                    print(f"  ... and {len(data_manager.values) - 30} more")

        elif cmd == "reload":
            data_manager.load_all_data()
            print(
                f"Data reloaded — {len(data_manager.values)} items | "
                f"{len(data_manager.chests)} chests"
            )

        elif cmd == "backup":
            try:
                bdir = os.path.join(config.BASE_DIR, "backups")
                os.makedirs(bdir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                bfile = os.path.join(bdir, f"values_backup_{ts}.json")
                with open(config.VALUES_PATH, "r", encoding="utf-8") as f:
                    bdata = json.load(f)
                with open(bfile, "w", encoding="utf-8") as f:
                    json.dump(bdata, f, indent=2, ensure_ascii=False)
                print(f"Backup created: {os.path.basename(bfile)} ({len(bdata)} items)")
            except Exception as e:
                print(f"Backup error: {e}")

        elif cmd == "maintenance":
            if args.lower() == "on":
                data_manager.settings["maintenance_mode"] = True
                data_manager.save_settings()
                print("Maintenance mode ENABLED")
            elif args.lower() == "off":
                data_manager.settings["maintenance_mode"] = False
                data_manager.save_settings()
                print("Maintenance mode DISABLED")
            else:
                state = "ON" if data_manager.settings.get("maintenance_mode") else "OFF"
                print(f"Maintenance mode is currently {state}. Use: maintenance on/off")

        elif cmd == "announce":
            if not args:
                print("Usage: announce <message>")
            else:
                async def _send_announce(msg_text):
                    embed = discord.Embed(
                        title="Announcement",
                        description=msg_text,
                        color=Colors.INFO,
                        timestamp=datetime.datetime.now()
                    )
                    embed.set_footer(text="Official announcement from the bot owner")
                    sent, failed = 0, 0
                    for guild in bot.guilds:
                        try:
                            channel = None
                            for ch in guild.text_channels:
                                if ch.permissions_for(guild.me).send_messages:
                                    if any(n in ch.name.lower() for n in ["general", "announce", "info"]):
                                        channel = ch
                                        break
                            if not channel:
                                for ch in guild.text_channels:
                                    if ch.permissions_for(guild.me).send_messages:
                                        channel = ch
                                        break
                            if channel:
                                await channel.send(embed=embed)
                                sent += 1
                                await asyncio.sleep(0.5)
                            else:
                                failed += 1
                        except:
                            failed += 1
                    print(f"Announcement sent to {sent} server(s) ({failed} failed)")
                asyncio.run_coroutine_threadsafe(_send_announce(args), bot.loop)

        elif cmd == "servers":
            if not bot.guilds:
                print("Bot is not in any servers.")
            else:
                print(f"\n{len(bot.guilds)} server(s):")
                for i, g in enumerate(sorted(bot.guilds, key=lambda x: x.member_count, reverse=True), 1):
                    print(f"  {i:02}. {g.name} — {g.member_count} members | ID: {g.id}")

        elif cmd == "polls":
            if not data_manager.active_polls:
                print("No active polls.")
            else:
                print(f"\n{len(data_manager.active_polls)} active poll(s):")
                for pid, p in data_manager.active_polls.items():
                    total = sum(p.get("counts", {}).values())
                    print(f"  • {p.get('item', '?')} — {total} vote(s) | ID: {pid}")

        elif cmd == "logs":
            try:
                n = int(args) if args else 10
            except ValueError:
                n = 10
            logs = data_manager.get_logs()
            recent = logs[-n:]
            if not recent:
                print("No logs found.")
            else:
                print(f"\nLast {len(recent)} log(s):")
                for log in reversed(recent):
                    print(
                        f"  [{log.get('date', '?')}] "
                        f"{log.get('action', '?')} — "
                        f"{log.get('item', '?')} by "
                        f"{log.get('user_name', '?')}"
                    )

        elif cmd == "clear":
            os.system("cls" if platform.system() == "Windows" else "clear")

        elif cmd == "help":
            print(CONSOLE_HELP)

        elif cmd in ("exit", "quit", "stop"):
            print("Shutting down bot...")
            asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
            break

        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")


@bot.tree.command(name="value", description="Display the value of an item")
@app_commands.describe(item="Item name")
@app_commands.autocomplete(item=item_autocomplete)
@global_command_check()
async def value_cmd(interaction: discord.Interaction, item: str):
    item_data = data_manager.values.get(item)
    if not item_data:
        return await interaction.response.send_message(f"Item **{item}** not found.", ephemeral=True)
    content = (
        f"{ANSI.WHITE}{ANSI.BOLD}Value:{ANSI.RESET} {ANSI.GREEN}{item_data['value']}{ANSI.RESET}\n"
        f"{ANSI.colorize('Demand', item_data['demand'])}\n"
        f"{ANSI.colorize('Stability', item_data['stability'])}\n"
        f"{ANSI.colorize('Overpay', item_data['overpay'])}"
    )
    embed = discord.Embed(
        title=f"**{item}**",
        description=f"```ansi\n{content}\n```",
        color=Colors.get(item_data["stability"])
    )
    if item_data.get("image"):
        embed.set_thumbnail(url=item_data["image"])
    if item_data.get("notes"):
        embed.set_footer(text=item_data["notes"])
    is_fav = item in data_manager.favorites.get(interaction.user.id, [])
    embed.add_field(
        name="Quick Actions",
        value="Favorited ⭐" if is_fav else "Use /addfavorite to save this item",
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="list", description="List all items sorted by value")
@app_commands.describe(page="Page number (default: 1)")
@global_command_check()
async def list_cmd(interaction: discord.Interaction, page: int = 1):
    def _val(t):
        try:
            return ValueParser.parse(t[1].get("value", "0"))
        except:
            return 0
    items = sorted(data_manager.values.items(), key=_val, reverse=True)
    total = len(items)
    if total == 0:
        return await interaction.response.send_message("No items in the list.", ephemeral=True)
    per_page = 25
    max_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, max_pages))
    chunk = items[(page - 1) * per_page: page * per_page]
    embed = discord.Embed(
        title=f"Item List — Page {page}/{max_pages}",
        description="Sorted by value (highest first)\n",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    lines = [
        f"`#{(page-1)*per_page+i+1:02}` {STABILITY_EMOJIS.get(d.get('stability', ''), '⚪')} "
        f"**{n}** — `{d.get('value', '?')}`"
        for i, (n, d) in enumerate(chunk)
    ]
    full = embed.description + "\n".join(lines)
    if len(full) > 4096:
        embed.description = "Sorted by value (highest first)\n\n" + "\n".join(lines[:20])
        embed.set_footer(text=f"Truncated • {total} total • Page {page}/{max_pages}")
    else:
        embed.description = full
        embed.set_footer(text=f"{total} item(s) • Page {page}/{max_pages}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="search", description="Search items using filters")
@app_commands.describe(
    name="Filter by name",
    demand="Filter by demand",
    stability="Filter by stability",
    overpay="Filter by overpay"
)
@app_commands.choices(demand=DEMAND_CHOICES, stability=STABILITY_CHOICES, overpay=OVERPAY_CHOICES)
@global_command_check()
async def search_cmd(
    interaction: discord.Interaction,
    name: str = "",
    demand: Optional[app_commands.Choice[str]] = None,
    stability: Optional[app_commands.Choice[str]] = None,
    overpay: Optional[app_commands.Choice[str]] = None
):
    data_manager.statistics["total_searches"] += 1
    data_manager.save_statistics()
    results = [
        (n, d) for n, d in data_manager.values.items()
        if (not name or name.lower() in n.lower())
        and (not demand or d.get("demand") == demand.value)
        and (not stability or d.get("stability") == stability.value)
        and (not overpay or d.get("overpay") == overpay.value)
    ]
    if not results:
        return await interaction.response.send_message("No results found.", ephemeral=True)
    embed = discord.Embed(
        title=f"Search Results — {len(results)} item(s)",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    lines = [
        f"{STABILITY_EMOJIS.get(d.get('stability', ''), '⚪')} **{n}** — "
        f"`{d.get('value', '?')}` | D:{d.get('demand', '?')[0]} S:{d.get('stability', '?')[0]}"
        for n, d in results[:20]
    ]
    if len(results) > 20:
        lines.append(f"*...and {len(results) - 20} more.*")
    embed.description = "\n".join(lines)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="compare", description="Compare two items side by side")
@app_commands.describe(item1="First item", item2="Second item")
@app_commands.autocomplete(item1=item_autocomplete, item2=item_autocomplete)
@global_command_check()
async def compare(interaction: discord.Interaction, item1: str, item2: str):
    d1 = data_manager.values.get(item1)
    d2 = data_manager.values.get(item2)
    if not d1:
        return await interaction.response.send_message(f"**{item1}** not found.", ephemeral=True)
    if not d2:
        return await interaction.response.send_message(f"**{item2}** not found.", ephemeral=True)
    embed = discord.Embed(title="Item Comparison", color=Colors.DEFAULT, timestamp=datetime.datetime.now())
    embed.add_field(
        name=f"{item1}",
        value=(
            f"Value: **{d1.get('value', '?')}**\n"
            f"Demand: {d1.get('demand', '?')}\n"
            f"Stability: {d1.get('stability', '?')}\n"
            f"Overpay: {d1.get('overpay', '?')}"
        ),
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name=f"{item2}",
        value=(
            f"Value: **{d2.get('value', '?')}**\n"
            f"Demand: {d2.get('demand', '?')}\n"
            f"Stability: {d2.get('stability', '?')}\n"
            f"Overpay: {d2.get('overpay', '?')}"
        ),
        inline=True
    )
    notes = []
    if d1.get("notes"):
        notes.append(f"**{item1}**: {d1['notes']}")
    if d2.get("notes"):
        notes.append(f"**{item2}**: {d2['notes']}")
    if notes:
        embed.add_field(name="Notes", value="\n".join(notes), inline=False)
    if d1.get("image"):
        embed.set_thumbnail(url=d1["image"])
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="calculator", description="Calculate the value of a trade")
@app_commands.describe(
    my_items="Your items, separated by commas",
    their_items="Their items, separated by commas"
)
@global_command_check()
async def calculator(interaction: discord.Interaction, my_items: str, their_items: str):
    def _parse(items_str):
        total, found, missing = 0, [], []
        for n in [i.strip() for i in items_str.split(",")]:
            d = data_manager.values.get(n)
            if d:
                try:
                    v = ValueParser.parse(d["value"])
                    total += v
                    found.append((n, d["value"]))
                except:
                    missing.append(n)
            else:
                missing.append(n)
        return found, total, missing

    my_found, my_total, my_miss = _parse(my_items)
    th_found, th_total, th_miss = _parse(their_items)
    diff = abs(my_total - th_total)

    if my_total > th_total:
        status, diff_t, color = "You overpay", f"-{ValueParser.format(diff)}", Colors.ERROR
    elif th_total > my_total:
        status, diff_t, color = "You profit", f"+{ValueParser.format(diff)}", Colors.SUCCESS
    else:
        status, diff_t, color = "Fair trade", "±0", Colors.MEDIUM

    embed = discord.Embed(
        title="Trade Calculator",
        description=f"**{status}** ({diff_t})",
        color=color,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name=f"You Give ({ValueParser.format(my_total)})",
        value="\n".join(f"• {n} (`{v}`)" for n, v in my_found) or "—",
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name=f"You Receive ({ValueParser.format(th_total)})",
        value="\n".join(f"• {n} (`{v}`)" for n, v in th_found) or "—",
        inline=True
    )
    all_miss = my_miss + th_miss
    if all_miss:
        embed.add_field(
            name="Not Found",
            value=", ".join(f"`{i}`" for i in all_miss),
            inline=False
        )
    embed.set_footer(text="Separate multiple items with commas")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="history", description="View modification history for an item")
@app_commands.describe(item="Item name")
@app_commands.autocomplete(item=item_autocomplete)
@global_command_check()
async def history(interaction: discord.Interaction, item: str):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    logs = [l for l in data_manager.get_logs() if l.get("item") == item]
    if not logs:
        return await interaction.response.send_message(f"No history found for **{item}**.", ephemeral=True)
    embed = discord.Embed(
        title=f"History — {item}",
        description=f"**{len(logs)}** event(s)",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    emoji_map = {
        "ADD REQUEST": "📥", "ADD ACCEPTED": "✅", "ADD REJECTED": "❌",
        "EDIT REQUEST": "✏️", "EDIT ACCEPTED": "✅", "EDIT REJECTED": "❌",
        "MODIFIED": "✏️", "DELETED": "🗑️", "ADMIN_ADD": "👑"
    }
    for log in reversed(logs[-10:]):
        action = log.get("action", "?")
        field_val = f"**{log.get('user_name', 'System')}** • `{log.get('date', '?')}`"
        if log.get("validator"):
            field_val += f"\nValidated by: {log['validator']}"
        if "changes" in log and isinstance(log["changes"], list):
            field_val += "\n" + "\n".join(f"  • {c}" for c in log["changes"][:3])
        elif "data" in log and isinstance(log["data"], dict) and log["data"].get("value"):
            field_val += f"\n  Value: {log['data']['value']}"
        embed.add_field(
            name=f"{emoji_map.get(action, '📌')} {action}",
            value=field_val,
            inline=False
        )
    embed.set_footer(
        text=f"Showing last 10 of {len(logs)}" if len(logs) > 10 else "Full history"
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="watch", description="Watch an item for value changes")
@app_commands.describe(item="Item to watch")
@app_commands.autocomplete(item=item_autocomplete)
@global_command_check()
async def watch(interaction: discord.Interaction, item: str):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    data_manager.watches.setdefault(item, [])
    if interaction.user.id in data_manager.watches[item]:
        return await interaction.response.send_message(
            f"You are already watching **{item}**.", ephemeral=True)
    data_manager.watches[item].append(interaction.user.id)
    data_manager.save_watches()
    embed = discord.Embed(
        title="Watch Activated",
        description=f"You'll receive a DM whenever **{item}** is updated.",
        color=Colors.SUCCESS
    )
    embed.add_field(name="Current Value", value=f"**{data_manager.values[item].get('value', '?')}**", inline=True)
    embed.set_footer(text="Use /unwatch to stop")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="unwatch", description="Stop watching an item")
@app_commands.describe(item="Item to unwatch (leave empty to see your list)")
@app_commands.autocomplete(item=item_autocomplete)
@global_command_check()
async def unwatch(interaction: discord.Interaction, item: str = ""):
    if not item:
        my = [obj for obj, users in data_manager.watches.items() if interaction.user.id in users]
        if not my:
            return await interaction.response.send_message(
                "You are not watching any items.", ephemeral=True)
        embed = discord.Embed(
            title="Your Watched Items",
            description="\n".join(f"• **{o}**" for o in my),
            color=Colors.DEFAULT
        )
        embed.set_footer(text="Use /unwatch item:<name> to stop watching")
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    if interaction.user.id not in data_manager.watches.get(item, []):
        return await interaction.response.send_message(
            f"You are not watching **{item}**.", ephemeral=True)
    data_manager.watches[item].remove(interaction.user.id)
    if not data_manager.watches[item]:
        del data_manager.watches[item]
    data_manager.save_watches()
    await interaction.response.send_message(
        f"You are no longer watching **{item}**.", ephemeral=True)


@bot.tree.command(name="profile", description="View your profile or another user's")
@app_commands.describe(user="User to view (optional)")
@global_command_check()
async def profile(interaction: discord.Interaction, user: discord.User = None):
    target = user or interaction.user
    p = data_manager.profiles.get(target.id)
    if not p:
        msg = (
            "No activity recorded yet. Use `/additem` or `/createpoll` to get started!"
            if target.id == interaction.user.id
            else f"**{target.name}** has no recorded activity."
        )
        return await interaction.response.send_message(msg, ephemeral=True)

    total_s = p.get("total_suggestions", 0)
    accepted = p.get("accepted_suggestions", 0)
    rejected = p.get("rejected_suggestions", 0)
    votes = p.get("poll_votes", 0)
    trades = p.get("total_trades", 0)
    commands = p.get("commands_used", 0)
    rate = (accepted / total_s * 100) if total_s > 0 else 0

    badges = []
    if total_s >= 1:   badges.append("First Contribution")
    if total_s >= 10:  badges.append("Active Contributor")
    if total_s >= 50:  badges.append("Expert Contributor")
    if accepted >= 5:  badges.append("Reliable")
    if accepted >= 20: badges.append("Very Reliable")
    if votes >= 10:    badges.append("Regular Voter")
    if votes >= 50:    badges.append("Poll Expert")
    if trades >= 10:   badges.append("Trader")
    if trades >= 50:   badges.append("Expert Trader")
    if commands >= 100: badges.append("Bot Enthusiast")

    pts = accepted * 10 + rejected * 2 + votes + trades * 3 + commands // 10
    if pts >= 500:   level, color = "Legend",   0xFFD700
    elif pts >= 200: level, color = "Diamond",  0x00FFFF
    elif pts >= 100: level, color = "Platinum", 0xE5E4E2
    elif pts >= 50:  level, color = "Gold",     Colors.VERY_HIGH
    elif pts >= 20:  level, color = "Silver",   Colors.HIGH
    else:            level, color = "Bronze",   Colors.MEDIUM

    embed = discord.Embed(
        title=f"Profile — {target.name}",
        color=color,
        timestamp=datetime.datetime.now()
    )
    embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else None)
    embed.add_field(name="Level", value=f"**{level}**\n`{pts} pts`", inline=True)
    embed.add_field(
        name="Suggestions",
        value=(
            f"Total: **{total_s}**\n"
            f"Accepted: **{accepted}**\n"
            f"Rejected: **{rejected}**\n"
            f"Rate: **{rate:.1f}%**"
        ),
        inline=True
    )
    embed.add_field(name="Votes",    value=f"**{votes}** vote(s)",   inline=True)
    embed.add_field(name="Trades",   value=f"**{trades}** trade(s)", inline=True)
    embed.add_field(name="Commands", value=f"**{commands}** used",   inline=True)
    wc = sum(1 for obj, users in data_manager.watches.items() if target.id in users)
    if wc:
        embed.add_field(name="Watching", value=f"**{wc}** item(s)", inline=True)
    if badges:
        embed.add_field(name=f"Badges ({len(badges)})", value="\n".join(badges), inline=False)
    embed.add_field(
        name="Activity",
        value=(
            f"First: `{p.get('first_activity', '?')}`\n"
            f"Last: `{p.get('last_activity', '?')}`"
        ),
        inline=False
    )
    embed.set_footer(text=f"ID: {target.id}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="heatmap", description="View a heatmap of items by demand and stability")
@global_command_check()
async def heatmap(interaction: discord.Interaction):
    await interaction.response.defer()
    if not data_manager.values:
        return await interaction.followup.send("No items available.", ephemeral=True)

    demands = ["Very Low", "Low", "Medium", "High", "Very High"]
    stabilities = ["Very Bad", "Bad", "Medium", "Good", "Very Good"]
    matrix = {d: {s: 0 for s in stabilities} for d in demands}

    for item in data_manager.values.values():
        d = item.get("demand", "Medium")
        s = item.get("stability", "Medium")
        if d in matrix and s in matrix[d]:
            matrix[d][s] += 1

    header = "```\nDemand      | V.Bad  Bad   Med  Good V.Good\n" + "─" * 42 + "\n"
    lines = []
    for d in demands:
        line = f"{d:11} |"
        for s in stabilities:
            line += "   ·  " if matrix[d][s] == 0 else f"  {matrix[d][s]:>3} "
        lines.append(line)

    embed = discord.Embed(
        title="Item Distribution Heatmap",
        description=f"Demand × Stability\n{header + chr(10).join(lines) + chr(10) + '```'}",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    combos = sorted(
        [(f"{d} + {s}", matrix[d][s]) for d in demands for s in stabilities if matrix[d][s] > 0],
        key=lambda x: x[1], reverse=True
    )
    if combos:
        embed.add_field(
            name="Top 5 Combinations",
            value="\n".join(f"• **{c}**: {n}" for c, n in combos[:5]),
            inline=False
        )
    embed.set_footer(text=f"{len(data_manager.values)} items total")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="leaderboard", description="View top contributors and traders")
@app_commands.describe(category="Leaderboard category")
@app_commands.choices(category=[
    app_commands.Choice(name="Top Contributors", value="contributors"),
    app_commands.Choice(name="Top Traders",      value="traders"),
    app_commands.Choice(name="Top Voters",       value="voters"),
    app_commands.Choice(name="Top Command Users",value="commands"),
])
@global_command_check()
async def leaderboard(interaction: discord.Interaction, category: app_commands.Choice[str]):
    await interaction.response.defer()
    cfg = {
        "contributors": ("accepted_suggestions", "Top Contributors", "accepted"),
        "traders":      ("total_trades",          "Top Traders",      "trades"),
        "voters":       ("poll_votes",            "Top Voters",       "votes"),
        "commands":     ("commands_used",         "Top Command Users","commands"),
    }[category.value]
    stat_key, title, stat_label = cfg
    sorted_users = sorted(
        data_manager.profiles.items(),
        key=lambda x: x[1].get(stat_key, 0),
        reverse=True
    )[:10]
    if not sorted_users:
        return await interaction.followup.send("No data available.", ephemeral=True)
    embed = discord.Embed(
        title=title,
        description=f"Top 10 users by {stat_label}\n",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, prof) in enumerate(sorted_users, 1):
        user = bot.get_user(uid)
        if not user:
            try:
                user = await bot.fetch_user(uid)
                username = user.name
            except:
                username = f"Unknown ({uid})"
        else:
            username = user.name
        medal = medals[i - 1] if i <= 3 else f"`#{i:02}`"
        embed.add_field(
            name=f"{medal} {username}",
            value=f"**{prof.get(stat_key, 0)}** {stat_label}",
            inline=False
        )
    embed.set_footer(text=f"Total profiles: {len(data_manager.profiles)}")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="help", description="Show all available commands")
@global_command_check()
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Help — Available Commands",
        description="Here is a list of all available commands:",
        color=Colors.DEFAULT
    )
    embed.add_field(name="Lookup",           value="`/value` `/list` `/search` `/compare` `/calculator` `/history`", inline=False)
    embed.add_field(name="Utilities",        value="`/watch` `/unwatch` `/profile` `/heatmap` `/leaderboard`", inline=False)
    embed.add_field(name="Favorites & Alerts",value="`/addfavorite` `/removefavorite` `/viewfavorites` `/setalert` `/viewalerts` `/removealert`", inline=False)
    embed.add_field(name="Polls & Trading",  value="`/createpoll` `/closepoll` `/logtrade` `/tradehistory` `/market`", inline=False)
    embed.add_field(name="Contributions",    value="`/additem` `/suggestmodify`", inline=False)
    embed.add_field(name="Information",      value="`/serverinfo` `/botinfo` `/statistics` `/locatechest` `/locatechestlist`", inline=False)
    if interaction.user.id == config.OWNER_ID:
        embed.add_field(
            name="Administration",
            value=(
                "`/adminadd` `/edititem` `/deleteitem` `/setvalue` `/massdelete`\n"
                "`/exportjson` `/importjson` `/clearhistory` `/userinfo` `/resetprofile`\n"
                "`/broadcastdm` `/itemstats` `/synccommands` `/cleanwatches` `/setbotname`\n"
                "`/addnote` `/pollstats` `/reload` `/dashboard` `/backup` `/loadbackup`\n"
                "`/announce` `/togglecommand` `/maintenance` `/banuser` `/serverinvite` `/globalstats`"
            ),
            inline=False
        )
    embed.set_footer(text="Tip: Use autocomplete to find commands faster!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="locatechest", description="Find a chest location by name")
@app_commands.describe(name="Chest name")
@app_commands.autocomplete(name=chest_autocomplete)
@global_command_check()
async def locatechest(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    data_manager.load_chests()
    if not data_manager.chests:
        return await interaction.followup.send("No chest locations found.", ephemeral=True)

    chest = None
    chest_index = None
    try:
        idx = int(name)
        if 0 <= idx < len(data_manager.chests):
            chest, chest_index = data_manager.chests[idx], idx
    except ValueError:
        for i, c in enumerate(data_manager.chests):
            if c.get("name", "").lower() == name.lower():
                chest, chest_index = c, i
                break
        if not chest:
            for i, c in enumerate(data_manager.chests):
                if name.lower() in c.get("name", "").lower():
                    chest, chest_index = c, i
                    break

    if not chest:
        return await interaction.followup.send(
            f"Chest **{name}** not found. Try using autocomplete.", ephemeral=True)

    cname = chest.get("name", "Unknown Chest")
    desc = chest.get("description", "No description available.")
    img = chest.get("image", "")
    nl = cname.lower()

    if "easy" in nl:
        dcol, demoji = Colors.SUCCESS, "🟢"
    elif "medium" in nl:
        dcol, demoji = Colors.WARNING, "🟡"
    elif "hard" in nl:
        dcol, demoji = Colors.ERROR, "🔴"
    else:
        dcol, demoji = Colors.DEFAULT, "📦"

    embed = discord.Embed(title=f"{demoji} {cname}", color=dcol, timestamp=datetime.datetime.now())
    embed.add_field(name="Clue", value=f"*{desc}*", inline=False)
    embed.set_footer(text=f"Chest #{chest_index + 1} of {len(data_manager.chests)}")

    is_url = img.startswith("http://") or img.startswith("https://")
    if is_url and img:
        embed.set_image(url=img)
        await interaction.followup.send(embed=embed)
    elif img and not is_url:
        full = os.path.join(config.BASE_DIR, img)
        if os.path.exists(full):
            fname = os.path.basename(full)
            f = discord.File(full, filename=fname)
            embed.set_image(url=f"attachment://{fname}")
            await interaction.followup.send(embed=embed, file=f)
        else:
            embed.add_field(name="Image", value=f"File not found: `{img}`", inline=False)
            await interaction.followup.send(embed=embed)
    else:
        embed.add_field(name="Image", value="No image available.", inline=False)
        await interaction.followup.send(embed=embed)


@bot.tree.command(name="locatechestlist", description="List all available chest locations")
@app_commands.describe(page="Page number", difficulty="Filter by difficulty")
@app_commands.choices(difficulty=[
    app_commands.Choice(name="Easy",   value="easy"),
    app_commands.Choice(name="Medium", value="medium"),
    app_commands.Choice(name="Hard",   value="hard"),
    app_commands.Choice(name="All",    value="all"),
])
@global_command_check()
async def locatechestlist(
    interaction: discord.Interaction,
    page: int = 1,
    difficulty: Optional[app_commands.Choice[str]] = None
):
    await interaction.response.defer()
    data_manager.load_chests()
    if not data_manager.chests:
        return await interaction.followup.send("No chest locations found.", ephemeral=True)

    filtered = [
        (i, c) for i, c in enumerate(data_manager.chests)
        if not difficulty or difficulty.value == "all"
        or difficulty.value in c.get("name", "").lower()
    ]
    if not filtered:
        return await interaction.followup.send("No chests match this filter.", ephemeral=True)

    per_page = 15
    total = len(filtered)
    max_pgs = (total + per_page - 1) // per_page
    page = max(1, min(page, max_pgs))
    chunk = filtered[(page - 1) * per_page: page * per_page]

    easy_c   = sum(1 for _, c in filtered if "easy"   in c.get("name", "").lower())
    medium_c = sum(1 for _, c in filtered if "medium" in c.get("name", "").lower())
    hard_c   = sum(1 for _, c in filtered if "hard"   in c.get("name", "").lower())
    other_c  = total - easy_c - medium_c - hard_c

    embed = discord.Embed(
        title=f"Chest Locations — Page {page}/{max_pgs}",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    parts = []
    if easy_c:   parts.append(f"🟢 {easy_c} Easy")
    if medium_c: parts.append(f"🟡 {medium_c} Medium")
    if hard_c:   parts.append(f"🔴 {hard_c} Hard")
    if other_c:  parts.append(f"📦 {other_c} Other")
    embed.description = f"**{total} chest(s)**\n{' • '.join(parts)}\n\n"

    lines = []
    for oi, c in chunk:
        cn = c.get("name", f"Chest #{oi + 1}")
        dsc = c.get("description", "No description")
        cnl = cn.lower()
        de = "🟢" if "easy" in cnl else "🟡" if "medium" in cnl else "🔴" if "hard" in cnl else "📦"
        sd = dsc[:60] + "..." if len(dsc) > 60 else dsc
        lines.append(
            f"`#{oi + 1:02}` {de} **{cn}** {'🖼️' if c.get('image') else ''}\n  ╰ *{sd}*"
        )
    embed.description += "\n".join(lines)
    if len(embed.description) > 4096:
        embed.description = embed.description[:4090] + "..."

    embed.set_footer(text=f"{total} chest(s) • Page {page}/{max_pgs}")
    embed.add_field(
        name="How to Use",
        value=(
            "`/locatechest name:<chest>` — View details\n"
            "`/locatechestlist difficulty:<filter>` — Filter by difficulty\n"
            "`/locatechestlist page:<n>` — Navigate pages"
        ),
        inline=False
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="addfavorite", description="Add an item to your favorites")
@app_commands.autocomplete(item=item_autocomplete)
@app_commands.describe(item="Item name")
@global_command_check()
async def addfavorite(interaction: discord.Interaction, item: str):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    favs = data_manager.favorites.setdefault(interaction.user.id, [])
    if len(favs) >= 25:
        return await interaction.response.send_message(
            "You have reached the maximum of 25 favorites.", ephemeral=True)
    if item in favs:
        return await interaction.response.send_message(
            f"**{item}** is already in your favorites.", ephemeral=True)
    favs.append(item)
    data_manager.save_favorites()
    embed = discord.Embed(
        title="Favorite Added",
        description=f"**{item}** has been added to your favorites.",
        color=Colors.SUCCESS
    )
    embed.add_field(name="Current Value", value=f"`{data_manager.values[item].get('value', '?')}`")
    embed.set_footer(text=f"You have {len(favs)} favorite(s)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="removefavorite", description="Remove an item from your favorites")
@app_commands.autocomplete(item=item_autocomplete)
@app_commands.describe(item="Item name")
@global_command_check()
async def removefavorite(interaction: discord.Interaction, item: str):
    favs = data_manager.favorites.get(interaction.user.id, [])
    if item not in favs:
        return await interaction.response.send_message(
            f"**{item}** is not in your favorites.", ephemeral=True)
    favs.remove(item)
    data_manager.save_favorites()
    await interaction.response.send_message(
        f"**{item}** removed from your favorites.", ephemeral=True)


@bot.tree.command(name="viewfavorites", description="View your favorite items")
@global_command_check()
async def viewfavorites(interaction: discord.Interaction):
    favs = data_manager.favorites.get(interaction.user.id, [])
    if not favs:
        return await interaction.response.send_message(
            "You have no favorites yet. Use `/addfavorite` to add some!", ephemeral=True)
    embed = discord.Embed(
        title=f"{interaction.user.name}'s Favorites",
        description=f"**{len(favs)}** favorite(s)\n",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    for item in favs[:25]:
        if item in data_manager.values:
            d = data_manager.values[item]
            em = STABILITY_EMOJIS.get(d.get("stability", ""), "⚪")
            embed.add_field(
                name=f"{em} {item}",
                value=f"`{d.get('value', '?')}` | D:{d.get('demand', '?')[0]} S:{d.get('stability', '?')[0]}",
                inline=False
            )
        else:
            embed.add_field(name=f"❌ {item}", value="*This item no longer exists*", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="setalert", description="Set a price alert for an item")
@app_commands.describe(
    item="Item name",
    condition="Alert condition",
    target_value="Target value (e.g. 500k, 1M)"
)
@app_commands.autocomplete(item=item_autocomplete)
@app_commands.choices(condition=[
    app_commands.Choice(name="Above",  value="above"),
    app_commands.Choice(name="Below",  value="below"),
    app_commands.Choice(name="Equals", value="equals"),
])
@global_command_check()
async def setalert(
    interaction: discord.Interaction,
    item: str,
    condition: app_commands.Choice[str],
    target_value: str
):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    try:
        target = ValueParser.parse(target_value)
    except ValueError as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

    alerts = data_manager.alerts.setdefault(interaction.user.id, [])
    for a in alerts:
        if a["item"] == item and a["condition"] == condition.value:
            return await interaction.response.send_message(
                f"You already have a **{condition.name}** alert for **{item}**.", ephemeral=True)

    alerts.append({
        "item": item, "condition": condition.value,
        "target_value": target, "created_at": get_timestamp(), "triggered": False
    })
    data_manager.save_alerts()
    embed = discord.Embed(
        title="Alert Created",
        description=(
            f"You'll be notified when **{item}** goes **{condition.name.lower()}** "
            f"`{ValueParser.format(target)}`"
        ),
        color=Colors.SUCCESS
    )
    embed.add_field(name="Current Value", value=f"`{data_manager.values[item].get('value', '?')}`", inline=True)
    embed.add_field(name="Target",        value=f"`{ValueParser.format(target)}`",                  inline=True)
    embed.set_footer(text=f"You have {len(alerts)} active alert(s)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="viewalerts", description="View your active price alerts")
@global_command_check()
async def viewalerts(interaction: discord.Interaction):
    alerts = data_manager.alerts.get(interaction.user.id, [])
    if not alerts:
        return await interaction.response.send_message(
            "No active alerts. Use `/setalert` to create one!", ephemeral=True)
    embed = discord.Embed(
        title="Your Price Alerts",
        description=f"**{len(alerts)}** alert(s)\n",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    cem = {"above": "📈", "below": "📉", "equals": "📊"}
    for i, a in enumerate(alerts, 1):
        cur = data_manager.values.get(a["item"], {}).get("value", "?")
        embed.add_field(
            name=f"{i}. {cem.get(a['condition'], '🔔')} {a['item']}",
            value=(
                f"Condition: **{a['condition'].capitalize()}** `{ValueParser.format(a['target_value'])}`\n"
                f"Current: `{cur}` | "
                f"Status: {'Triggered' if a.get('triggered') else 'Active'}"
            ),
            inline=False
        )
    embed.set_footer(text="Use /removealert to delete an alert")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="removealert", description="Remove a price alert")
@app_commands.describe(index="Alert number (from /viewalerts)")
@global_command_check()
async def removealert(interaction: discord.Interaction, index: int):
    alerts = data_manager.alerts.get(interaction.user.id, [])
    if not alerts:
        return await interaction.response.send_message("You have no active alerts.", ephemeral=True)
    if index < 1 or index > len(alerts):
        return await interaction.response.send_message(
            f"Invalid number. You have **{len(alerts)}** alert(s).", ephemeral=True)
    removed = alerts.pop(index - 1)
    data_manager.save_alerts()
    embed = discord.Embed(
        title="Alert Removed",
        description=f"Alert for **{removed['item']}** has been deleted.",
        color=Colors.SUCCESS
    )
    embed.add_field(
        name="Details",
        value=f"Condition: **{removed['condition']}** `{ValueParser.format(removed['target_value'])}`"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="logtrade", description="Log a trade you made")
@global_command_check()
async def logtrade(interaction: discord.Interaction):
    await interaction.response.send_modal(TradeModal())


@bot.tree.command(name="tradehistory", description="View your trade history")
@app_commands.describe(user="User to view (optional)")
@global_command_check()
async def tradehistory(interaction: discord.Interaction, user: discord.User = None):
    target = user or interaction.user
    trades = [t for t in data_manager.trades if t.get("user_id") == target.id]
    if not trades:
        msg = (
            "No trades logged yet. Use `/logtrade` to log one!"
            if target.id == interaction.user.id
            else f"**{target.name}** has no logged trades."
        )
        return await interaction.response.send_message(msg, ephemeral=True)
    embed = discord.Embed(
        title=f"{target.name}'s Trade History",
        description=f"**{len(trades)}** trade(s)\n",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    for i, t in enumerate(reversed(trades[-10:]), 1):
        embed.add_field(
            name=f"Trade #{len(trades) - i + 1}",
            value=(
                f"Gave: {', '.join(t['items_given'])}\n"
                f"Received: {', '.join(t['items_received'])}\n"
                f"Partner: {t.get('partner', 'Unknown')}\n"
                f"{t.get('timestamp', '?')}"
            ),
            inline=False
        )
    if len(trades) > 10:
        embed.set_footer(text=f"Showing last 10 of {len(trades)} trades")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="market", description="View market analysis and trends")
@app_commands.describe(category="Analysis category")
@app_commands.choices(category=[
    app_commands.Choice(name="Trending Items",   value="trending"),
    app_commands.Choice(name="High Value Items", value="high_value"),
    app_commands.Choice(name="High Demand",      value="high_demand"),
    app_commands.Choice(name="Market Overview",  value="overview"),
])
@global_command_check()
async def market(interaction: discord.Interaction, category: app_commands.Choice[str]):
    await interaction.response.defer()

    def _sv(t):
        try:
            return ValueParser.parse(t[1].get("value", "0"))
        except:
            return 0

    if category.value == "high_value":
        top = sorted(data_manager.values.items(), key=_sv, reverse=True)[:10]
        embed = discord.Embed(
            title="Top 10 Highest Value Items",
            color=Colors.PURPLE,
            timestamp=datetime.datetime.now()
        )
        for i, (n, d) in enumerate(top, 1):
            embed.add_field(
                name=f"{i}. {STABILITY_EMOJIS.get(d.get('stability', ''), '⚪')} {n}",
                value=(
                    f"`{d.get('value', '?')}` | "
                    f"Demand: {d.get('demand', '?')} | "
                    f"Stability: {d.get('stability', '?')}"
                ),
                inline=False
            )

    elif category.value == "high_demand":
        hi = sorted(
            [(n, d) for n, d in data_manager.values.items()
             if d.get("demand") in ("High", "Very High")],
            key=_sv, reverse=True
        )
        embed = discord.Embed(
            title="High Demand Items",
            description=f"**{len(hi)}** item(s)\n",
            color=Colors.ORANGE,
            timestamp=datetime.datetime.now()
        )
        for n, d in hi[:15]:
            embed.add_field(
                name=f"{STABILITY_EMOJIS.get(d.get('stability', ''), '⚪')} {n}",
                value=f"`{d.get('value', '?')}` | {d.get('demand', '?')}",
                inline=True
            )

    elif category.value == "overview":
        total = len(data_manager.values)
        dc, sc = defaultdict(int), defaultdict(int)
        for d in data_manager.values.values():
            dc[d.get("demand", "?")] += 1
            sc[d.get("stability", "?")] += 1
        embed = discord.Embed(
            title="Market Overview",
            description=f"Analysis of **{total}** items",
            color=Colors.INFO,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(
            name="Demand",
            value="\n".join(
                f"{k}: **{v}** ({v / total * 100:.1f}%)"
                for k, v in sorted(dc.items(), key=lambda x: x[1], reverse=True)
            ),
            inline=True
        )
        embed.add_field(
            name="Stability",
            value="\n".join(
                f"{STABILITY_EMOJIS.get(k, '⚪')} {k}: **{v}** ({v / total * 100:.1f}%)"
                for k, v in sorted(sc.items(), key=lambda x: x[1], reverse=True)
            ),
            inline=True
        )
        embed.add_field(
            name="Activity",
            value=(
                f"Trades: **{len(data_manager.trades)}**\n"
                f"Polls: **{data_manager.statistics.get('total_polls_created', 0)}**\n"
                f"Searches: **{data_manager.statistics.get('total_searches', 0)}**"
            ),
            inline=False
        )

    else:
        mc = defaultdict(int)
        for log in data_manager.get_logs()[-50:]:
            if log.get("action") in ("MODIFIED", "EDIT ACCEPTED") and log.get("item"):
                mc[log["item"]] += 1
        trending = sorted(mc.items(), key=lambda x: x[1], reverse=True)[:10]
        embed = discord.Embed(
            title="Trending Items",
            description="Recently modified items\n",
            color=Colors.WARNING,
            timestamp=datetime.datetime.now()
        )
        for i, (n, count) in enumerate(trending, 1):
            if n in data_manager.values:
                d = data_manager.values[n]
                embed.add_field(
                    name=f"{i}. {STABILITY_EMOJIS.get(d.get('stability', ''), '⚪')} {n}",
                    value=f"`{d.get('value', '?')}` | {count} change(s)",
                    inline=False
                )

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="serverinfo", description="View server statistics")
@global_command_check()
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    if not g:
        return await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True)
    bots = sum(1 for m in g.members if m.bot)
    humans = g.member_count - bots
    embed = discord.Embed(
        title=g.name,
        color=Colors.INFO,
        timestamp=datetime.datetime.now()
    )
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(
        name="Members",
        value=f"Total: **{g.member_count}**\nHumans: **{humans}**\nBots: **{bots}**",
        inline=True
    )
    embed.add_field(
        name="Channels",
        value=(
            f"Text: **{len(g.text_channels)}**\n"
            f"Voice: **{len(g.voice_channels)}**\n"
            f"Categories: **{len(g.categories)}**"
        ),
        inline=True
    )
    embed.add_field(name="Roles",   value=f"**{len(g.roles)}**",  inline=True)
    embed.add_field(name="Emojis",  value=f"**{len(g.emojis)}**", inline=True)
    embed.add_field(
        name="Boosts",
        value=f"Level: **{g.premium_tier}**\n**{g.premium_subscription_count or 0}** boost(s)",
        inline=True
    )
    embed.add_field(name="Owner",   value=g.owner.mention,                                inline=True)
    embed.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:R>",       inline=False)
    embed.set_footer(text=f"Server ID: {g.id}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="botinfo", description="View information about the bot")
@global_command_check()
async def botinfo(interaction: discord.Interaction):
    proc = psutil.Process()
    mem = proc.memory_info().rss / 1024 / 1024
    embed = discord.Embed(
        title=bot.user.name,
        description="Value List & Trading Bot",
        color=Colors.INFO,
        timestamp=datetime.datetime.now()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(
        name="Statistics",
        value=(
            f"Servers: **{len(bot.guilds)}**\n"
            f"Users: **{sum(g.member_count for g in bot.guilds)}**\n"
            f"Commands Used: **{data_manager.statistics.get('total_commands_used', 0)}**\n"
            f"Items: **{len(data_manager.values)}**\n"
            f"Trades: **{len(data_manager.trades)}**"
        ),
        inline=True
    )
    embed.add_field(
        name="System",
        value=(
            f"Python: **{platform.python_version()}**\n"
            f"discord.py: **{discord.__version__}**\n"
            f"Memory: **{mem:.1f} MB**\n"
            f"OS: **{platform.system()} {platform.release()}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Uptime",
        value=f"Started: `{data_manager.statistics.get('uptime_start', '?')}`",
        inline=False
    )
    top5 = sorted(
        data_manager.statistics.get("commands_breakdown", {}).items(),
        key=lambda x: x[1], reverse=True
    )[:5]
    if top5:
        embed.add_field(
            name="Most Used Commands",
            value="\n".join(f"`/{c}`: **{n}** uses" for c, n in top5),
            inline=False
        )
    embed.set_footer(text=f"Bot ID: {bot.user.id}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="statistics", description="View detailed bot statistics")
@global_command_check()
async def statistics_cmd(interaction: discord.Interaction):
    s = data_manager.statistics
    embed = discord.Embed(title="Bot Statistics", color=Colors.INFO, timestamp=datetime.datetime.now())
    embed.add_field(name="Commands",  value=f"Total: **{s.get('total_commands_used', 0)}**", inline=True)
    embed.add_field(name="Searches",  value=f"Total: **{s.get('total_searches', 0)}**",      inline=True)
    embed.add_field(
        name="Polls",
        value=(
            f"Created: **{s.get('total_polls_created', 0)}**\n"
            f"Active: **{len(data_manager.active_polls)}**"
        ),
        inline=True
    )
    embed.add_field(name="Trades",    value=f"Logged: **{len(data_manager.trades)}**",       inline=True)
    embed.add_field(
        name="Servers",
        value=(
            f"Current: **{len(bot.guilds)}**\n"
            f"Joined: **{s.get('servers_joined', 0)}**\n"
            f"Left: **{s.get('servers_left', 0)}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Users",
        value=(
            f"Profiles: **{len(data_manager.profiles)}**\n"
            f"Favorites: **{sum(len(f) for f in data_manager.favorites.values())}**\n"
            f"Alerts: **{sum(len(a) for a in data_manager.alerts.values())}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Data",
        value=(
            f"Items: **{len(data_manager.values)}**\n"
            f"Chests: **{len(data_manager.chests)}**\n"
            f"Logs: **{len(data_manager.get_logs())}**"
        ),
        inline=True
    )
    tw = sum(len(u) for u in data_manager.watches.values())
    embed.add_field(
        name="Watches",
        value=f"Total: **{tw}**\nItems: **{len(data_manager.watches)}**",
        inline=True
    )
    top3 = sorted(
        s.get("commands_breakdown", {}).items(),
        key=lambda x: x[1], reverse=True
    )[:3]
    if top3:
        embed.add_field(
            name="Top Commands",
            value=" • ".join(f"`/{c}`" for c, _ in top3),
            inline=False
        )
    embed.set_footer(text=f"Tracking since {s.get('uptime_start', '?')}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="additem", description="Propose adding a new item to the list")
@app_commands.describe(
    item="Item name", value="Value (e.g. 7.5k)",
    demand="Demand level", stability="Stability level",
    overpay="Overpay level", image="Image URL (optional)", notes="Notes (optional)"
)
@app_commands.choices(demand=DEMAND_CHOICES, stability=STABILITY_CHOICES, overpay=OVERPAY_CHOICES)
@global_command_check()
async def additem(
    interaction: discord.Interaction,
    item: str, value: str,
    demand: app_commands.Choice[str],
    stability: app_commands.Choice[str],
    overpay: app_commands.Choice[str],
    image: str = "", notes: str = ""
):
    await interaction.response.defer(ephemeral=True)
    if item in data_manager.values:
        return await interaction.followup.send(
            f"**{item}** already exists. Use `/suggestmodify` to suggest changes.", ephemeral=True)

    data = {
        "value": value, "demand": demand.value,
        "stability": stability.value, "overpay": overpay.value,
        "image": image, "notes": notes
    }
    embed = discord.Embed(
        title=f"Add Request — {item}",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Requested by", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="Item",      value=f"**{item}**",          inline=True)
    embed.add_field(name="Value",     value=f"**{value}**",          inline=True)
    embed.add_field(name="Demand",    value=f"**{demand.value}**",   inline=True)
    embed.add_field(name="Stability", value=f"**{stability.value}**",inline=True)
    embed.add_field(name="Overpay",   value=f"**{overpay.value}**",  inline=True)
    if image:
        embed.add_field(name="Image", value=image, inline=False)
        embed.set_thumbnail(url=image)
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text="React ✅ to accept or ❌ to reject")

    try:
        owner = await bot.fetch_user(config.OWNER_ID)
        dm_msg = await owner.send(embed=embed)
        await dm_msg.add_reaction("✅")
        await dm_msg.add_reaction("❌")
        data_manager.pending_requests[dm_msg.id] = {
            "type": "add", "item": item, "data": data,
            "user_id": interaction.user.id, "user_name": str(interaction.user)
        }
        data_manager.update_profile(interaction.user.id, "suggestion")
        data_manager.save_log(create_log_entry("ADD REQUEST", item, interaction.user, data=data))
        await interaction.followup.send(
            f"Your request for **{item}** has been sent to the owner.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("Could not contact the bot owner.", ephemeral=True)


@bot.tree.command(name="suggestmodify", description="Suggest a modification to an existing item")
@app_commands.describe(
    item="Item name", value="New value", demand="New demand",
    stability="New stability", overpay="New overpay",
    image="New image URL", notes="New notes"
)
@app_commands.choices(demand=DEMAND_CHOICES, stability=STABILITY_CHOICES, overpay=OVERPAY_CHOICES)
@app_commands.autocomplete(item=item_autocomplete)
@global_command_check()
async def suggestmodify(
    interaction: discord.Interaction,
    item: str, value: str = "",
    demand: Optional[app_commands.Choice[str]] = None,
    stability: Optional[app_commands.Choice[str]] = None,
    overpay: Optional[app_commands.Choice[str]] = None,
    image: str = "", notes: str = ""
):
    await interaction.response.defer(ephemeral=True)
    if item not in data_manager.values:
        return await interaction.followup.send(
            f"**{item}** does not exist. Use `/additem` to add it.", ephemeral=True)

    old = data_manager.values[item]
    data = {
        "value": value,
        "demand":    demand.value    if demand    else "",
        "stability": stability.value if stability else "",
        "overpay":   overpay.value   if overpay   else "",
        "image": image, "notes": notes
    }
    if not any(data.values()):
        return await interaction.followup.send(
            "You must modify at least one field.", ephemeral=True)

    embed = discord.Embed(
        title=f"Modification Suggestion — {item}",
        color=Colors.WARNING,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="Suggested by",
        value=f"{interaction.user.mention} (`{interaction.user.id}`)",
        inline=False
    )
    field_map = {
        "value":     ("Value",     old.get("value",     "—")),
        "demand":    ("Demand",    old.get("demand",    "—")),
        "stability": ("Stability", old.get("stability", "—")),
        "overpay":   ("Overpay",   old.get("overpay",   "—")),
        "image":     ("Image",     old.get("image",     "—")),
        "notes":     ("Notes",     old.get("notes",     "—")),
    }
    for key, (label, old_val) in field_map.items():
        if data.get(key):
            embed.add_field(
                name=label,
                value=f"~~{old_val}~~ → **{data[key]}**",
                inline=True
            )
    embed.set_footer(text="React ✅ to accept or ❌ to reject")

    try:
        vch = bot.get_channel(config.VALIDATION_CHANNEL_ID)
        if not vch:
            return await interaction.followup.send(
                "Validation channel not found.", ephemeral=True)
        vmsg = await vch.send(embed=embed)
        await vmsg.add_reaction("✅")
        await vmsg.add_reaction("❌")
        data_manager.pending_requests[vmsg.id] = {
            "type": "edit", "item": item, "data": data, "old": old.copy(),
            "user_id": interaction.user.id, "user_name": str(interaction.user),
            "channel_type": "public"
        }
        data_manager.update_profile(interaction.user.id, "suggestion")
        data_manager.save_log(create_log_entry("EDIT REQUEST", item, interaction.user, old=old, new=data))
        await interaction.followup.send(
            f"Your suggestion for **{item}** has been submitted.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("Cannot send to the validation channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


@bot.tree.command(name="createpoll", description="Create a value poll for an item")
@app_commands.describe(item="Item name")
@app_commands.autocomplete(item=item_autocomplete)
@global_command_check()
async def createpoll(interaction: discord.Interaction, item: str):
    data_manager.statistics["total_polls_created"] += 1
    data_manager.save_statistics()
    await interaction.response.defer()

    if item not in data_manager.values:
        return await interaction.followup.send(f"**{item}** does not exist.", ephemeral=True)
    for p in data_manager.active_polls.values():
        if p["item"] == item:
            return await interaction.followup.send(
                f"A poll is already active for **{item}**.", ephemeral=True)

    d = data_manager.values[item]
    embed = discord.Embed(
        title=f"Value Poll — {item}",
        description=(
            "Click the button to propose a value.\n\n"
            "You can change your vote at any time.\n"
            "The average is calculated in real-time.\n"
            "The owner will close the poll when ready."
        ),
        color=Colors.get(d.get("stability", "Medium")),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="Current Value",
        value=(
            f"`{d.get('value', '?')}`\n"
            f"Demand: `{d.get('demand', '?')}`\n"
            f"Stability: `{d.get('stability', '?')}`\n"
            f"Overpay: `{d.get('overpay', '?')}`"
        ),
        inline=False
    )
    if d.get("image"):
        embed.set_thumbnail(url=d["image"])
    embed.set_footer(text="Use /closepoll to close this poll")
    msg = await interaction.followup.send(embed=embed)
    data_manager.active_polls[msg.id] = {
        "item": item, "author": interaction.user.id, "votes": {}, "counts": {}
    }
    data_manager.save_active_polls()
    await msg.edit(view=PollView(msg.id))


@bot.tree.command(name="closepoll", description="[Owner] Close an active poll")
@app_commands.describe(poll="Select an active poll")
@app_commands.autocomplete(poll=poll_autocomplete)
@owner_only()
@global_command_check()
async def closepoll(interaction: discord.Interaction, poll: str):
    poll_id = int(poll)
    poll_data = data_manager.active_polls.get(poll_id)
    if not poll_data:
        return await interaction.response.send_message("This poll no longer exists.", ephemeral=True)

    counts = poll_data["counts"]
    item = poll_data["item"]
    if not counts:
        return await interaction.response.send_message(
            "No votes have been cast on this poll.", ephemeral=True)

    total_votes = sum(counts.values())
    average = sum(v * c for v, c in counts.items()) / total_votes
    result = ValueParser.format(int(average))
    old_value = data_manager.values[item].get("value", "?")

    if item in data_manager.values:
        data_manager.values[item]["value"] = result
        data_manager.save_values()

    sorted_votes = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    vote_details = "\n".join(
        f"• **{ValueParser.format(v)}** — {c} vote(s)" for v, c in sorted_votes
    )

    try:
        msg = await interaction.channel.fetch_message(poll_id)
        embed = msg.embeds[0]
        embed.color = Colors.SUCCESS
        embed.add_field(
            name="Final Result",
            value=f"**{result}**\n{total_votes} vote(s)\n\n{vote_details}",
            inline=False
        )
        embed.set_footer(text=f"Poll closed on {get_timestamp()}")
        await msg.edit(embed=embed, view=None)
    except discord.NotFound:
        pass

    if old_value != result and item in data_manager.watches:
        wn = discord.Embed(
            title=f"{item} has been updated!",
            description=f"**{old_value}** → **{result}**\n\n*Updated from poll results*",
            color=Colors.WARNING,
            timestamp=datetime.datetime.now()
        )
        wn.set_footer(text="You are watching this item • /unwatch to stop")
        for uid in data_manager.watches[item]:
            try:
                u = await bot.fetch_user(uid)
                await u.send(f"<@{uid}>", embed=wn)
            except:
                pass

    del data_manager.active_polls[poll_id]
    data_manager.save_active_polls()
    await interaction.response.send_message(
        f"Poll closed for **{item}**: **{result}** ({total_votes} votes)", ephemeral=True)


@bot.tree.command(name="adminadd", description="[Owner] Add an item directly without approval")
@app_commands.describe(
    item="Item name", value="Value", demand="Demand",
    stability="Stability", overpay="Overpay",
    image="Image URL", notes="Notes"
)
@app_commands.choices(demand=DEMAND_CHOICES, stability=STABILITY_CHOICES, overpay=OVERPAY_CHOICES)
@owner_only()
@global_command_check()
async def adminadd(
    interaction: discord.Interaction,
    item: str, value: str,
    demand: app_commands.Choice[str],
    stability: app_commands.Choice[str],
    overpay: app_commands.Choice[str],
    image: str = "", notes: str = ""
):
    if item in data_manager.values:
        return await interaction.response.send_message(
            f"**{item}** already exists. Use `/edititem` to modify it.", ephemeral=True)
    data = {
        "value": value, "demand": demand.value,
        "stability": stability.value, "overpay": overpay.value,
        "image": image, "notes": notes
    }
    data_manager.values[item] = data
    data_manager.save_values()
    data_manager.save_log(create_log_entry("ADMIN_ADD", item, interaction.user, data=data))

    embed = discord.Embed(
        title=f"Item Added — {item}",
        color=Colors.SUCCESS,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Value",     value=f"**{value}**",          inline=True)
    embed.add_field(name="Demand",    value=f"**{demand.value}**",   inline=True)
    embed.add_field(name="Stability", value=f"**{stability.value}**",inline=True)
    embed.add_field(name="Overpay",   value=f"**{overpay.value}**",  inline=True)
    if image:
        embed.set_thumbnail(url=image)
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text=f"Added on {get_timestamp()}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="edititem", description="[Owner] Edit an existing item")
@app_commands.describe(
    item="Item name", value="New value", demand="New demand",
    stability="New stability", overpay="New overpay",
    image="New image URL", notes="New notes"
)
@app_commands.autocomplete(item=item_autocomplete)
@app_commands.choices(demand=DEMAND_CHOICES, stability=STABILITY_CHOICES, overpay=OVERPAY_CHOICES)
@owner_only()
@global_command_check()
async def edititem(
    interaction: discord.Interaction,
    item: str, value: str = "",
    demand: Optional[app_commands.Choice[str]] = None,
    stability: Optional[app_commands.Choice[str]] = None,
    overpay: Optional[app_commands.Choice[str]] = None,
    image: str = "", notes: str = ""
):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)

    d = data_manager.values[item]
    changes = []
    old_value = d.get("value", "?")
    val_changed = False

    if value:
        changes.append(f"value: `{d['value']}` → `{value}`")
        d["value"] = value
        val_changed = True
    if demand:
        changes.append(f"demand: `{d['demand']}` → `{demand.value}`")
        d["demand"] = demand.value
    if stability:
        changes.append(f"stability: `{d['stability']}` → `{stability.value}`")
        d["stability"] = stability.value
    if overpay:
        changes.append(f"overpay: `{d['overpay']}` → `{overpay.value}`")
        d["overpay"] = overpay.value
    if image:
        changes.append("image updated")
        d["image"] = image
    if notes:
        changes.append("notes updated")
        d["notes"] = notes

    if not changes:
        return await interaction.response.send_message("No changes provided.", ephemeral=True)

    data_manager.values[item] = d
    data_manager.save_values()
    data_manager.save_log(create_log_entry("MODIFIED", item, interaction.user, changes=changes))

    if val_changed and item in data_manager.watches:
        wn = discord.Embed(
            title=f"{item} has been updated!",
            description=f"**{old_value}** → **{value}**",
            color=Colors.WARNING,
            timestamp=datetime.datetime.now()
        )
        wn.add_field(
            name="New Stats",
            value=(
                f"Value: **{value}**\n"
                f"Demand: {d.get('demand', '?')}\n"
                f"Stability: {d.get('stability', '?')}\n"
                f"Overpay: {d.get('overpay', '?')}"
            )
        )
        wn.add_field(name="Modified by", value=f"**{interaction.user}** (Owner)", inline=False)
        wn.set_footer(text="You are watching this item • /unwatch to stop")
        for uid in data_manager.watches[item]:
            try:
                u = await bot.fetch_user(uid)
                await u.send(f"<@{uid}>", embed=wn)
            except:
                pass

    embed = discord.Embed(
        title=f"Item Modified — {item}",
        color=Colors.WARNING,
        timestamp=datetime.datetime.now()
    )
    embed.description = "\n".join(f"• {c}" for c in changes)
    if val_changed and item in data_manager.watches:
        embed.set_footer(text=f"{len(data_manager.watches[item])} watcher(s) notified")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="deleteitem", description="[Owner] Delete an item from the list")
@app_commands.autocomplete(item=item_autocomplete)
@app_commands.describe(item="Item name to delete")
@owner_only()
@global_command_check()
async def deleteitem(interaction: discord.Interaction, item: str):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    del data_manager.values[item]
    data_manager.save_values()
    data_manager.save_log(create_log_entry("DELETED", item, interaction.user))
    await interaction.response.send_message(f"**{item}** has been deleted.", ephemeral=True)


@bot.tree.command(name="reload", description="[Owner] Reload all data files")
@owner_only()
@global_command_check()
async def reload_cmd(interaction: discord.Interaction):
    try:
        data_manager.load_all_data()
        await interaction.response.send_message(
            f"Data reloaded.\n"
            f"Items: **{len(data_manager.values)}** | "
            f"Chests: **{len(data_manager.chests)}** | "
            f"Profiles: **{len(data_manager.profiles)}**",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@bot.tree.command(name="backup", description="[Owner] Create a backup of the value list")
@owner_only()
@global_command_check()
async def backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        bdir = os.path.join(config.BASE_DIR, "backups")
        os.makedirs(bdir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bfile = os.path.join(bdir, f"values_backup_{ts}.json")
        with open(config.VALUES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(bfile, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        bkps = [x for x in os.listdir(bdir) if x.startswith("values_backup_")]
        embed = discord.Embed(
            title="Backup Created",
            description=f"`{os.path.basename(bfile)}`",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Items",   value=f"**{len(data)}**",             inline=True)
        embed.add_field(name="Total",   value=f"**{len(bkps)}** backup(s)",   inline=True)
        embed.add_field(name="Size",    value=f"**{os.path.getsize(bfile) / 1024:.1f} KB**", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Backup error: {e}", ephemeral=True)


@bot.tree.command(name="loadbackup", description="[Owner] Restore a backup")
@app_commands.describe(backup_file="Backup filename (leave empty to list available backups)")
@owner_only()
@global_command_check()
async def loadbackup(interaction: discord.Interaction, backup_file: str = ""):
    await interaction.response.defer(ephemeral=True)
    bdir = os.path.join(config.BASE_DIR, "backups")

    if not backup_file:
        if not os.path.exists(bdir):
            return await interaction.followup.send("No backups found.", ephemeral=True)
        bkps = sorted(
            [x for x in os.listdir(bdir) if x.startswith("values_backup_")],
            reverse=True
        )
        if not bkps:
            return await interaction.followup.send("No backups available.", ephemeral=True)
        embed = discord.Embed(
            title="Available Backups",
            description=f"**{len(bkps)}** backup(s)",
            color=Colors.DEFAULT,
            timestamp=datetime.datetime.now()
        )
        lines = []
        for i, bk in enumerate(bkps[:10], 1):
            try:
                dto = datetime.datetime.strptime(
                    bk.replace("values_backup_", "").replace(".json", ""), "%Y%m%d_%H%M%S")
                fd = dto.strftime("%m/%d/%Y at %H:%M:%S")
            except:
                fd = "Unknown date"
            lines.append(
                f"`{i}.` **{bk}**\n"
                f"   {fd} • {os.path.getsize(os.path.join(bdir, bk)) / 1024:.1f} KB"
            )
        embed.description = "\n\n".join(lines)
        embed.set_footer(text="Use /loadbackup backup_file:<filename> to restore")
        return await interaction.followup.send(embed=embed, ephemeral=True)

    bpath = os.path.join(bdir, backup_file)
    if not os.path.exists(bpath):
        return await interaction.followup.send(f"Backup **{backup_file}** not found.", ephemeral=True)

    try:
        sbk = os.path.join(
            bdir, f"before_restore_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(config.VALUES_PATH, "r", encoding="utf-8") as f:
            cur = json.load(f)
        with open(sbk, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=2, ensure_ascii=False)
        with open(bpath, "r", encoding="utf-8") as f:
            bdata = json.load(f)
        with open(config.VALUES_PATH, "w", encoding="utf-8") as f:
            json.dump(bdata, f, indent=2, ensure_ascii=False)
        data_manager.load_values()
        data_manager.save_log({
            "date": get_timestamp(), "action": "BACKUP RESTORED",
            "item": backup_file, "user_name": str(interaction.user),
            "user_id": interaction.user.id,
            "items_before": len(cur), "items_after": len(bdata)
        })
        embed = discord.Embed(
            title="Backup Restored",
            description=f"`{backup_file}`",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(
            name="Statistics",
            value=(
                f"Before: {len(cur)}\n"
                f"After: {len(bdata)}\n"
                f"Difference: {len(bdata) - len(cur):+d}"
            ),
            inline=True
        )
        embed.add_field(name="Safety Backup", value=f"`{os.path.basename(sbk)}`", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except json.JSONDecodeError:
        await interaction.followup.send(f"**{backup_file}** is corrupted.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Restore error: {e}", ephemeral=True)


@bot.tree.command(name="dashboard", description="[Owner] View global statistics dashboard")
@owner_only()
@global_command_check()
async def dashboard(interaction: discord.Interaction):
    logs = data_manager.get_logs()
    dc, sc, ac = {}, {}, {}
    for item in data_manager.values.values():
        dc[item.get("demand", "?")] = dc.get(item.get("demand", "?"), 0) + 1
        sc[item.get("stability", "?")] = sc.get(item.get("stability", "?"), 0) + 1
    for log in logs:
        a = log.get("action", "?")
        ac[a] = ac.get(a, 0) + 1
    recent = [l for l in logs if "REQUEST" in l.get("action", "")][-5:]

    embed = discord.Embed(title="Dashboard", color=Colors.DEFAULT, timestamp=datetime.datetime.now())
    embed.add_field(
        name="Stats",
        value=(
            f"**{len(data_manager.values)}** items\n"
            f"**{len(logs)}** logs\n"
            f"**{len(data_manager.pending_requests)}** pending\n"
            f"**{len(data_manager.active_polls)}** polls\n"
            f"**{len(data_manager.chests)}** chests\n"
            f"**{len(data_manager.trades)}** trades"
        ),
        inline=True
    )
    dord = ["Very Low", "Low", "Medium", "High", "Very High"]
    embed.add_field(
        name="Demand",
        value="\n".join(f"`{k:<10}` {dc.get(k, 0):>3}" for k in dord if dc.get(k, 0) > 0) or "—",
        inline=True
    )
    sord = ["Very Bad", "Bad", "Medium", "Good", "Very Good"]
    embed.add_field(
        name="Stability",
        value="\n".join(f"`{k:<10}` {sc.get(k, 0):>3}" for k in sord if sc.get(k, 0) > 0) or "—",
        inline=True
    )
    aord = [
        "ADD REQUEST", "ADD ACCEPTED", "ADD REJECTED",
        "EDIT REQUEST", "EDIT ACCEPTED", "EDIT REJECTED",
        "MODIFIED", "DELETED", "ADMIN_ADD"
    ]
    embed.add_field(
        name="Actions",
        value="\n".join(
            f"`{k:<16}` {ac.get(k, 0):>3}x" for k in aord if ac.get(k, 0) > 0) or "—",
        inline=False
    )
    if recent:
        embed.add_field(
            name="Recent Requests",
            value="\n".join(
                f"• **{l['item']}** by `{l.get('user_name', '?')}`"
                for l in reversed(recent)
            ),
            inline=False
        )
    embed.set_footer(text=f"Generated on {get_timestamp()}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="announce", description="[Owner] Send a global announcement to all servers")
@app_commands.describe(title="Announcement title", message="Announcement content", type="Type")
@app_commands.choices(type=[
    app_commands.Choice(name="Information", value="info"),
    app_commands.Choice(name="Warning",     value="warning"),
    app_commands.Choice(name="News",        value="success"),
    app_commands.Choice(name="Maintenance", value="maintenance"),
])
@owner_only()
@global_command_check()
async def announce(
    interaction: discord.Interaction,
    title: str, message: str,
    type: app_commands.Choice[str]
):
    await interaction.response.defer(ephemeral=True)
    cmap = {
        "info": Colors.DEFAULT, "warning": Colors.WARNING,
        "success": Colors.SUCCESS, "maintenance": Colors.ERROR
    }
    emap = {"info": "📢", "warning": "⚠️", "success": "🎉", "maintenance": "🔧"}
    embed = discord.Embed(
        title=f"{emap[type.value]} {title}",
        description=message,
        color=cmap[type.value],
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(
        text=f"Official announcement • {interaction.user}",
        icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
    )
    sent, failed = 0, 0
    for guild in bot.guilds:
        try:
            channel = None
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    if any(n in ch.name.lower() for n in ["general", "announce", "info"]):
                        channel = ch
                        break
            if not channel:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break
            if channel:
                await channel.send(embed=embed)
                sent += 1
                await asyncio.sleep(0.5)
            else:
                failed += 1
        except discord.RateLimited as e:
            await asyncio.sleep(e.retry_after)
        except:
            failed += 1

    re = discord.Embed(title="Announcement Sent", color=Colors.SUCCESS, timestamp=datetime.datetime.now())
    re.add_field(
        name="Results",
        value=f"Sent: **{sent}**\nFailed: **{failed}**\nTotal: **{len(bot.guilds)}**"
    )
    data_manager.save_log({
        "date": get_timestamp(), "action": "GLOBAL ANNOUNCEMENT",
        "item": title, "user_name": str(interaction.user),
        "user_id": interaction.user.id,
        "servers_reached": sent, "message": message
    })
    await interaction.followup.send(embed=re, ephemeral=True)


@bot.tree.command(name="togglecommand", description="[Owner] Enable or disable a command")
@app_commands.describe(command="Command name", enabled="Enable or disable")
@app_commands.autocomplete(command=command_autocomplete)
@owner_only()
@global_command_check()
async def togglecommand(interaction: discord.Interaction, command: str, enabled: bool):
    data_manager.toggle_command(command, enabled)
    embed = discord.Embed(
        title="Command Updated",
        description=f"`/{command}` is now **{'enabled' if enabled else 'disabled'}**",
        color=Colors.SUCCESS if enabled else Colors.ERROR
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="maintenance", description="[Owner] Toggle maintenance mode")
@app_commands.describe(enabled="Enable or disable maintenance mode")
@owner_only()
@global_command_check()
async def maintenance(interaction: discord.Interaction, enabled: bool):
    data_manager.settings["maintenance_mode"] = enabled
    data_manager.save_settings()
    embed = discord.Embed(
        title="Maintenance Mode",
        description=(
            f"Maintenance is now **{'enabled' if enabled else 'disabled'}**\n\n"
            + ("Only the owner can use commands." if enabled else "All users can use commands normally.")
        ),
        color=Colors.WARNING if enabled else Colors.SUCCESS
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="banuser", description="[Owner] Ban or unban a user from using the bot")
@app_commands.describe(user="User", action="Ban or unban")
@app_commands.choices(action=[
    app_commands.Choice(name="Ban",   value="ban"),
    app_commands.Choice(name="Unban", value="unban"),
])
@owner_only()
@global_command_check()
async def banuser(interaction: discord.Interaction, user: discord.User, action: app_commands.Choice[str]):
    banned = data_manager.settings.setdefault("banned_users", [])
    if action.value == "ban":
        if user.id in banned:
            return await interaction.response.send_message(
                f"**{user}** is already banned.", ephemeral=True)
        banned.append(user.id)
        data_manager.save_settings()
        embed = discord.Embed(
            title="User Banned",
            description=f"**{user}** (`{user.id}`) has been banned.",
            color=Colors.ERROR
        )
    else:
        if user.id not in banned:
            return await interaction.response.send_message(
                f"**{user}** is not banned.", ephemeral=True)
        banned.remove(user.id)
        data_manager.save_settings()
        embed = discord.Embed(
            title="User Unbanned",
            description=f"**{user}** (`{user.id}`) can use the bot again.",
            color=Colors.SUCCESS
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="serverinvite", description="[Owner] List all servers with invite links")
@owner_only()
@global_command_check()
async def serverinvite(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    servers_data = []
    for guild in bot.guilds:
        try:
            invite_url = None
            try:
                invites = await guild.invites()
                if invites:
                    invite_url = invites[0].url
            except discord.Forbidden:
                pass
            if not invite_url:
                try:
                    for ch in guild.text_channels:
                        if ch.permissions_for(guild.me).create_instant_invite:
                            inv = await ch.create_invite(max_age=300, max_uses=1)
                            invite_url = inv.url
                            break
                except discord.Forbidden:
                    pass
            servers_data.append({
                "name": guild.name, "id": guild.id,
                "members": guild.member_count,
                "owner": guild.owner.name if guild.owner else "Unknown",
                "invite": invite_url or "No permission"
            })
        except Exception as e:
            print(f"Error for {guild.name}: {e}")

    if not servers_data:
        return await interaction.followup.send("Bot is not in any servers.", ephemeral=True)

    servers_data.sort(key=lambda x: x["members"], reverse=True)
    embeds = []
    embed = discord.Embed(
        title="Servers with Bot",
        description=f"**Total: {len(servers_data)} server(s)**\n\n",
        color=Colors.INFO,
        timestamp=datetime.datetime.now()
    )
    fc = 0
    for i, srv in enumerate(servers_data, 1):
        it = (
            f"[Join Server]({srv['invite']})"
            if srv["invite"].startswith("http")
            else srv["invite"]
        )
        embed.add_field(
            name=f"#{i} {srv['name']}",
            value=f"**{srv['members']}** members | {srv['owner']}\n{it}\n`{srv['id']}`"[:1024],
            inline=False
        )
        fc += 1
        if fc >= 10 or i == len(servers_data):
            embed.set_footer(text=f"Page {len(embeds) + 1} • Total: {len(servers_data)}")
            embeds.append(embed)
            if i < len(servers_data):
                embed = discord.Embed(
                    title="Servers (continued)",
                    color=Colors.INFO,
                    timestamp=datetime.datetime.now()
                )
                fc = 0

    for e in embeds:
        await interaction.followup.send(embed=e, ephemeral=True)

    tm = sum(s["members"] for s in servers_data)
    se = discord.Embed(title="Server Summary", color=Colors.DEFAULT, timestamp=datetime.datetime.now())
    se.add_field(
        name="Statistics",
        value=(
            f"Total Servers: {len(servers_data)}\n"
            f"Total Members: {tm:,}\n"
            f"Average: {tm // len(servers_data)}\n"
            f"Largest: {servers_data[0]['name']} ({servers_data[0]['members']})\n"
            f"Smallest: {servers_data[-1]['name']} ({servers_data[-1]['members']})"
        ),
        inline=False
    )
    await interaction.followup.send(embed=se, ephemeral=True)


@bot.tree.command(name="setvalue", description="[Owner] Quickly update the value of an item")
@app_commands.describe(item="Item name", new_value="New value (e.g. 500k, 1.5M)")
@app_commands.autocomplete(item=item_autocomplete)
@owner_only()
@global_command_check()
async def setvalue(interaction: discord.Interaction, item: str, new_value: str):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    old = data_manager.values[item].get("value", "?")
    data_manager.values[item]["value"] = new_value
    data_manager.save_values()
    data_manager.save_log(create_log_entry(
        "MODIFIED", item, interaction.user,
        changes=[f"value: `{old}` → `{new_value}`"]
    ))
    if item in data_manager.watches:
        wn = discord.Embed(
            title=f"{item} value updated!",
            description=f"**{old}** → **{new_value}**",
            color=Colors.WARNING,
            timestamp=datetime.datetime.now()
        )
        wn.set_footer(text="You are watching this item • /unwatch to stop")
        for uid in data_manager.watches[item]:
            try:
                u = await bot.fetch_user(uid)
                await u.send(f"<@{uid}>", embed=wn)
            except:
                pass
    embed = discord.Embed(
        title="Value Updated",
        description=f"**{item}**\n`{old}` → `{new_value}`",
        color=Colors.SUCCESS,
        timestamp=datetime.datetime.now()
    )
    if item in data_manager.watches:
        embed.set_footer(text=f"{len(data_manager.watches[item])} watcher(s) notified")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="massdelete", description="[Owner] Delete multiple items at once")
@app_commands.describe(items="Items to delete, separated by commas")
@owner_only()
@global_command_check()
async def massdelete(interaction: discord.Interaction, items: str):
    await interaction.response.defer(ephemeral=True)
    deleted, not_found = [], []
    for item in [i.strip() for i in items.split(",")]:
        if item in data_manager.values:
            del data_manager.values[item]
            deleted.append(item)
            data_manager.save_log(create_log_entry("DELETED", item, interaction.user))
        else:
            not_found.append(item)
    if deleted:
        data_manager.save_values()
    embed = discord.Embed(title="Mass Delete", color=Colors.WARNING, timestamp=datetime.datetime.now())
    if deleted:
        embed.add_field(
            name=f"Deleted ({len(deleted)})",
            value="\n".join(f"• **{i}**" for i in deleted),
            inline=False
        )
    if not_found:
        embed.add_field(
            name=f"Not Found ({len(not_found)})",
            value="\n".join(f"• `{i}`" for i in not_found),
            inline=False
        )
    embed.set_footer(text=f"Remaining items: {len(data_manager.values)}")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="exportjson", description="[Owner] Export the value list as a JSON file")
@app_commands.describe(include_metadata="Include notes and images in the export")
@owner_only()
@global_command_check()
async def exportjson(interaction: discord.Interaction, include_metadata: bool = True):
    await interaction.response.defer(ephemeral=True)
    export = (
        data_manager.values if include_metadata
        else {
            n: {
                "value": d.get("value", ""),
                "demand": d.get("demand", ""),
                "stability": d.get("stability", ""),
                "overpay": d.get("overpay", "")
            }
            for n, d in data_manager.values.items()
        }
    )
    jb = json.dumps(export, indent=2, ensure_ascii=False).encode("utf-8")
    jf = discord.File(
        io.BytesIO(jb),
        filename=f"values_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    embed = discord.Embed(
        title="Value List Exported",
        description=f"**{len(export)}** items exported",
        color=Colors.SUCCESS,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Size",     value=f"`{len(jb) / 1024:.1f} KB`",                     inline=True)
    embed.add_field(name="Items",    value=f"**{len(export)}**",                               inline=True)
    embed.add_field(name="Metadata", value="Included" if include_metadata else "Excluded",     inline=True)
    await interaction.followup.send(embed=embed, file=jf, ephemeral=True)


@bot.tree.command(name="clearhistory", description="[Owner] Clear the bot logs")
@app_commands.describe(
    confirm="Type 'CONFIRM' to confirm",
    keep_last="Number of recent logs to keep (0 = delete all)"
)
@owner_only()
@global_command_check()
async def clearhistory(interaction: discord.Interaction, confirm: str, keep_last: int = 0):
    if confirm != "CONFIRM":
        return await interaction.response.send_message(
            "Type `CONFIRM` exactly to proceed.", ephemeral=True)
    logs = data_manager.get_logs()
    total = len(logs)
    kept = logs[-keep_last:] if keep_last > 0 else []
    with open(config.LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)
    data_manager._logs_dirty = True
    embed = discord.Embed(
        title="History Cleared",
        color=Colors.SUCCESS,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Before",  value=f"**{total}** logs",           inline=True)
    embed.add_field(name="Deleted", value=f"**{total - len(kept)}** logs",inline=True)
    embed.add_field(name="Kept",    value=f"**{len(kept)}** logs",        inline=True)
    embed.set_footer(text=f"Cleared by {interaction.user}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="userinfo", description="[Owner] View detailed information about a user")
@app_commands.describe(user="Target user")
@owner_only()
@global_command_check()
async def userinfo(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    p = data_manager.profiles.get(user.id, {})
    is_banned = user.id in data_manager.settings.get("banned_users", [])
    watched = [item for item, users in data_manager.watches.items() if user.id in users]

    embed = discord.Embed(
        title=f"User Info — {user.name}",
        color=Colors.ERROR if is_banned else Colors.INFO,
        timestamp=datetime.datetime.now()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="Status",  value="BANNED" if is_banned else "Active", inline=True)
    embed.add_field(name="ID",      value=f"`{user.id}`",                      inline=True)
    embed.add_field(name="Created", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)

    if p:
        embed.add_field(
            name="Activity",
            value=(
                f"Suggestions: **{p.get('total_suggestions', 0)}**\n"
                f"Accepted: **{p.get('accepted_suggestions', 0)}**\n"
                f"Votes: **{p.get('poll_votes', 0)}**\n"
                f"Trades: **{p.get('total_trades', 0)}**\n"
                f"Commands: **{p.get('commands_used', 0)}**"
            ),
            inline=True
        )
        embed.add_field(
            name="Dates",
            value=(
                f"First: `{p.get('first_activity', '?')}`\n"
                f"Last: `{p.get('last_activity', '?')}`"
            ),
            inline=True
        )
    embed.add_field(
        name="Data",
        value=(
            f"Watching: **{len(watched)}**\n"
            f"Favorites: **{len(data_manager.favorites.get(user.id, []))}**\n"
            f"Alerts: **{len(data_manager.alerts.get(user.id, []))}**\n"
            f"Trades: **{len([t for t in data_manager.trades if t.get('user_id') == user.id])}**"
        ),
        inline=True
    )
    mutual = [g for g in bot.guilds if g.get_member(user.id)]
    embed.add_field(name="Mutual Servers", value=f"**{len(mutual)}**", inline=True)
    embed.set_footer(text=f"Requested by {interaction.user}")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="resetprofile", description="[Owner] Reset a user's profile")
@app_commands.describe(user="User to reset", confirm="Type 'CONFIRM' to confirm")
@owner_only()
@global_command_check()
async def resetprofile(interaction: discord.Interaction, user: discord.User, confirm: str):
    if confirm != "CONFIRM":
        return await interaction.response.send_message(
            f"Type `CONFIRM` to reset **{user.name}**'s profile.", ephemeral=True)
    if user.id not in data_manager.profiles:
        return await interaction.response.send_message(
            f"**{user.name}** has no profile.", ephemeral=True)
    old = data_manager.profiles.pop(user.id)
    data_manager.save_profiles()
    embed = discord.Embed(
        title="Profile Reset",
        description=f"**{user.name}**'s profile has been reset.",
        color=Colors.WARNING,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="Previous Stats",
        value=(
            f"Suggestions: **{old.get('total_suggestions', 0)}**\n"
            f"Accepted: **{old.get('accepted_suggestions', 0)}**\n"
            f"Commands: **{old.get('commands_used', 0)}**\n"
            f"Trades: **{old.get('total_trades', 0)}**"
        )
    )
    embed.set_footer(text=f"Reset by {interaction.user}")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    try:
        await user.send(
            "Your bot profile has been reset by an administrator. "
            "All your statistics have been cleared."
        )
    except:
        pass


@bot.tree.command(name="broadcastdm", description="[Owner] Send a DM to all item watchers")
@app_commands.describe(message="Message to send", item="Specific item (optional)")
@app_commands.autocomplete(item=item_autocomplete)
@owner_only()
@global_command_check()
async def broadcastdm(interaction: discord.Interaction, message: str, item: str = ""):
    await interaction.response.defer(ephemeral=True)
    targets: set = set()
    if item:
        targets.update(data_manager.watches.get(item, []))
    else:
        for users in data_manager.watches.values():
            targets.update(users)
    if not targets:
        return await interaction.followup.send(
            f"No watchers found{f' for **{item}**' if item else ''}.", ephemeral=True)

    embed = discord.Embed(
        title="Message from Admin",
        description=message,
        color=Colors.INFO,
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text="Sent by the bot administrator")
    if item:
        embed.add_field(name="Related Item", value=f"**{item}**", inline=False)

    sent, failed = 0, 0
    for uid in targets:
        try:
            u = await bot.fetch_user(uid)
            await u.send(embed=embed)
            sent += 1
        except:
            failed += 1

    re = discord.Embed(title="Broadcast Sent", color=Colors.SUCCESS, timestamp=datetime.datetime.now())
    re.add_field(
        name="Results",
        value=f"Sent: **{sent}**\nFailed: **{failed}**\nTotal: **{len(targets)}**",
        inline=True
    )
    re.add_field(
        name="Target",
        value=f"**{item}** watchers" if item else "All watchers",
        inline=True
    )
    re.add_field(name="Message", value=message[:500], inline=False)
    await interaction.followup.send(embed=re, ephemeral=True)


@bot.tree.command(name="itemstats", description="[Owner] View detailed statistics for an item")
@app_commands.describe(item="Item name")
@app_commands.autocomplete(item=item_autocomplete)
@owner_only()
@global_command_check()
async def itemstats(interaction: discord.Interaction, item: str):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    d = data_manager.values[item]
    logs = data_manager.get_logs()
    item_logs = [l for l in logs if l.get("item") == item]
    ac = defaultdict(int)
    for l in item_logs:
        ac[l.get("action", "?")] += 1
    watchers = data_manager.watches.get(item, [])
    fav_count = sum(1 for fs in data_manager.favorites.values() if item in fs)
    alert_count = sum(
        1 for als in data_manager.alerts.values()
        for a in als if a.get("item") == item
    )
    embed = discord.Embed(
        title=f"Item Stats — {item}",
        color=Colors.get(d.get("stability", "Medium")),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="Current Values",
        value=(
            f"Value: **{d.get('value', '?')}**\n"
            f"Demand: **{d.get('demand', '?')}**\n"
            f"Stability: **{d.get('stability', '?')}**\n"
            f"Overpay: **{d.get('overpay', '?')}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Popularity",
        value=(
            f"Watchers: **{len(watchers)}**\n"
            f"Favorited: **{fav_count}**\n"
            f"Alerts: **{alert_count}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Log History",
        value=(
            f"Total: **{len(item_logs)}**\n"
            f"Accepted: **{ac.get('ADD ACCEPTED', 0) + ac.get('EDIT ACCEPTED', 0)}**\n"
            f"Rejected: **{ac.get('ADD REJECTED', 0) + ac.get('EDIT REJECTED', 0)}**\n"
            f"Modified: **{ac.get('MODIFIED', 0)}**\n"
            f"Requests: **{ac.get('ADD REQUEST', 0) + ac.get('EDIT REQUEST', 0)}**"
        ),
        inline=False
    )
    if d.get("notes"):
        embed.add_field(name="Notes", value=d["notes"], inline=False)
    if item_logs:
        ll = item_logs[-1]
        embed.add_field(
            name="Last Event",
            value=f"`{ll.get('action', '?')}` by **{ll.get('user_name', 'System')}**\n`{ll.get('date', '?')}`",
            inline=False
        )
    if d.get("image"):
        embed.set_thumbnail(url=d["image"])
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="synccommands", description="[Owner] Force re-sync slash commands")
@app_commands.describe(guild_only="Sync only to the current server (faster)")
@owner_only()
@global_command_check()
async def synccommands(interaction: discord.Interaction, guild_only: bool = False):
    await interaction.response.defer(ephemeral=True)
    try:
        if guild_only and interaction.guild:
            bot.tree.copy_global_to(guild=interaction.guild)
            synced = await bot.tree.sync(guild=interaction.guild)
            scope = f"Server: **{interaction.guild.name}**"
        else:
            synced = await bot.tree.sync()
            scope = "Global"
        embed = discord.Embed(
            title="Commands Synchronized",
            description=f"**{len(synced)}** command(s) synced",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Scope",    value=scope,                inline=True)
        embed.add_field(name="Commands", value=f"**{len(synced)}**", inline=True)
        embed.set_footer(text="Note: Global sync can take up to 1 hour to propagate")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Sync error: `{e}`", ephemeral=True)


@bot.tree.command(name="cleanwatches", description="[Owner] Remove watches for deleted items")
@owner_only()
@global_command_check()
async def cleanwatches(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    orphaned = [i for i in data_manager.watches if i not in data_manager.values]
    affected = set()
    for item in orphaned:
        for uid in data_manager.watches[item]:
            affected.add(uid)
        del data_manager.watches[item]
    data_manager.save_watches()
    embed = discord.Embed(title="Watches Cleaned", color=Colors.SUCCESS, timestamp=datetime.datetime.now())
    embed.add_field(name="Removed",    value=f"**{len(orphaned)}**",               inline=True)
    embed.add_field(name="Affected",   value=f"**{len(affected)}**",               inline=True)
    embed.add_field(name="Remaining",  value=f"**{len(data_manager.watches)}**",   inline=True)
    if orphaned:
        txt = "\n".join(f"• `{i}`" for i in orphaned[:10])
        if len(orphaned) > 10:
            txt += f"\n*...and {len(orphaned) - 10} more*"
        embed.add_field(name="Removed Items", value=txt, inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setbotname", description="[Owner] Change the bot's username")
@app_commands.describe(name="New bot name (2–32 characters)")
@owner_only()
@global_command_check()
async def setbotname(interaction: discord.Interaction, name: str):
    if not (2 <= len(name) <= 32):
        return await interaction.response.send_message(
            "Name must be between 2 and 32 characters.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    old = bot.user.name
    try:
        await bot.user.edit(username=name)
        embed = discord.Embed(
            title="Bot Name Updated",
            description=f"`{old}` → `{name}`",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="Discord limits username changes to 2 per hour")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"Could not change name: `{e}`\nLimit: 2 changes per hour.", ephemeral=True)


@bot.tree.command(name="addnote", description="[Owner] Add or update a note for an item")
@app_commands.describe(item="Item name", note="Note (leave empty to remove)")
@app_commands.autocomplete(item=item_autocomplete)
@owner_only()
@global_command_check()
async def addnote(interaction: discord.Interaction, item: str, note: str = ""):
    if item not in data_manager.values:
        return await interaction.response.send_message(f"**{item}** not found.", ephemeral=True)
    old_note = data_manager.values[item].get("notes", "")
    data_manager.values[item]["notes"] = note
    data_manager.save_values()
    data_manager.save_log(create_log_entry(
        "MODIFIED", item, interaction.user,
        changes=[f"notes: `{old_note or 'None'}` → `{note or 'Removed'}`"]
    ))
    if note:
        embed = discord.Embed(
            title=f"Note Added — {item}",
            description=f"**New note:**\n{note}",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        if old_note:
            embed.add_field(name="Previous Note", value=old_note, inline=False)
    else:
        embed = discord.Embed(
            title=f"Note Removed — {item}",
            description=f"Note removed from **{item}**.",
            color=Colors.WARNING,
            timestamp=datetime.datetime.now()
        )
        if old_note:
            embed.add_field(name="Removed Note", value=old_note, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="pollstats", description="[Owner] View statistics for all active polls")
@owner_only()
@global_command_check()
async def pollstats(interaction: discord.Interaction):
    if not data_manager.active_polls:
        return await interaction.response.send_message("No active polls.", ephemeral=True)
    embed = discord.Embed(
        title=f"Active Polls ({len(data_manager.active_polls)})",
        color=Colors.DEFAULT,
        timestamp=datetime.datetime.now()
    )
    for pid, poll in data_manager.active_polls.items():
        item = poll.get("item", "Unknown")
        counts = poll.get("counts", {})
        total = sum(counts.values())
        if total > 0:
            avg = int(sum(v * c for v, c in counts.items()) / total)
            avg_str = ValueParser.format(avg)
            top_str = ValueParser.format(
                sorted(counts.items(), key=lambda x: x[1], reverse=True)[0][0]
            )
        else:
            avg_str = top_str = "No votes"
        cur = data_manager.values.get(item, {}).get("value", "?")
        embed.add_field(
            name=f"{item}",
            value=(
                f"Votes: **{total}**\n"
                f"Average: **{avg_str}**\n"
                f"Top vote: **{top_str}**\n"
                f"Current: `{cur}`\n"
                f"Poll ID: `{pid}`"
            ),
            inline=True
        )
    embed.set_footer(
        text=f"Total polls created: {data_manager.statistics.get('total_polls_created', 0)}"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="importjson", description="[Owner] Import items from a JSON file attachment")
@app_commands.describe(merge="Merge with existing items (True) or replace all (False)")
@owner_only()
@global_command_check()
async def importjson(interaction: discord.Interaction, merge: bool = True):
    await interaction.response.send_message(
        "Send the JSON file as an attachment within the next **60 seconds**.",
        ephemeral=True
    )

    def check(m):
        return (
            m.author.id == interaction.user.id
            and m.channel.id == interaction.channel_id
            and m.attachments
            and m.attachments[0].filename.endswith(".json")
        )

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        attachment = msg.attachments[0]
        if attachment.size > 5 * 1024 * 1024:
            return await interaction.followup.send("File too large (max 5MB).", ephemeral=True)
        content = await attachment.read()
        imported = json.loads(content.decode("utf-8"))
        if not isinstance(imported, dict):
            return await interaction.followup.send("Invalid JSON format.", ephemeral=True)

        before = len(data_manager.values)
        new_cnt = updated_cnt = 0
        if merge:
            for name, data in imported.items():
                if name in data_manager.values:
                    updated_cnt += 1
                else:
                    new_cnt += 1
                data_manager.values[name] = data
        else:
            new_cnt = len(imported)
            data_manager.values = imported
        data_manager.save_values()
        data_manager.save_log({
            "date": get_timestamp(), "action": "JSON IMPORT",
            "item": attachment.filename, "user_name": str(interaction.user),
            "user_id": interaction.user.id,
            "items_imported": len(imported), "merge": merge
        })
        try:
            await msg.delete()
        except:
            pass

        embed = discord.Embed(
            title="Import Successful",
            description=f"Imported from `{attachment.filename}`",
            color=Colors.SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Before", value=f"**{before}**",                  inline=True)
        embed.add_field(name="After",  value=f"**{len(data_manager.values)}**", inline=True)
        embed.add_field(name="Mode",   value="Merge" if merge else "Replace",   inline=True)
        if merge:
            embed.add_field(name="New",     value=f"**{new_cnt}**",     inline=True)
            embed.add_field(name="Updated", value=f"**{updated_cnt}**", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    except asyncio.TimeoutError:
        await interaction.followup.send("Time expired. No file received.", ephemeral=True)
    except json.JSONDecodeError:
        await interaction.followup.send("Invalid JSON file.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Import error: `{e}`", ephemeral=True)


@bot.tree.command(name="globalstats", description="[Owner] View complete global statistics")
@owner_only()
@global_command_check()
async def globalstats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / 1024 / 1024
    cpu_pct = psutil.cpu_percent(interval=1)
    file_sizes = {}
    for name, path in [
        ("values.json",   config.VALUES_PATH),
        ("logs.json",     config.LOG_PATH),
        ("profiles.json", config.PROFILES_PATH),
        ("watches.json",  config.WATCHES_PATH),
        ("trades.json",   config.TRADES_PATH),
    ]:
        if os.path.exists(path):
            file_sizes[name] = os.path.getsize(path) / 1024

    embed = discord.Embed(
        title="Global Bot Statistics",
        description=f"Complete overview as of `{get_timestamp()}`",
        color=Colors.PURPLE,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="Servers & Users",
        value=(
            f"Servers: **{len(bot.guilds)}**\n"
            f"Members: **{sum(g.member_count for g in bot.guilds):,}**\n"
            f"Profiles: **{len(data_manager.profiles)}**\n"
            f"Banned: **{len(data_manager.settings.get('banned_users', []))}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Content",
        value=(
            f"Items: **{len(data_manager.values)}**\n"
            f"Chests: **{len(data_manager.chests)}**\n"
            f"Logs: **{len(data_manager.get_logs())}**\n"
            f"Active Polls: **{len(data_manager.active_polls)}**"
        ),
        inline=True
    )
    embed.add_field(
        name="User Data",
        value=(
            f"Watches: **{sum(len(u) for u in data_manager.watches.values())}**\n"
            f"Favorites: **{sum(len(f) for f in data_manager.favorites.values())}**\n"
            f"Alerts: **{sum(len(a) for a in data_manager.alerts.values())}**\n"
            f"Trades: **{len(data_manager.trades)}**"
        ),
        inline=True
    )
    embed.add_field(
        name="System",
        value=(
            f"Memory: **{mem_mb:.1f} MB**\n"
            f"CPU: **{cpu_pct:.1f}%**\n"
            f"Python: **{platform.python_version()}**\n"
            f"discord.py: **{discord.__version__}**"
        ),
        inline=True
    )
    embed.add_field(
        name="Usage",
        value=(
            f"Commands: **{data_manager.statistics.get('total_commands_used', 0):,}**\n"
            f"Searches: **{data_manager.statistics.get('total_searches', 0):,}**\n"
            f"Polls: **{data_manager.statistics.get('total_polls_created', 0)}**\n"
            f"Maintenance: **{'ON' if data_manager.settings.get('maintenance_mode') else 'OFF'}**"
        ),
        inline=True
    )
    embed.add_field(
        name="File Sizes",
        value="\n".join(f"`{n}`: **{s:.1f} KB**" for n, s in file_sizes.items()) or "N/A",
        inline=True
    )
    top5 = sorted(
        data_manager.statistics.get("commands_breakdown", {}).items(),
        key=lambda x: x[1], reverse=True
    )[:5]
    if top5:
        embed.add_field(
            name="Top 5 Commands",
            value="\n".join(f"`/{c}` — **{n}** uses" for c, n in top5),
            inline=False
        )
    embed.set_footer(text=f"Uptime since: {data_manager.statistics.get('uptime_start', '?')}")
    await interaction.followup.send(embed=embed, ephemeral=True)


if __name__ == "__main__":
    if not config.TOKEN or config.TOKEN == "YOUR_TOKEN_HERE":
        print("DISCORD_TOKEN not set. Update the TOKEN field in the Config class.")
        exit(1)
    try:
        bot.run(config.TOKEN)
    except discord.LoginFailure:
        print("Invalid token. Check your Config.")
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Critical error: {e}")