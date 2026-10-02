import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks

# --- CONFIGURATION ---
BOT_TOKEN = "MTU1NTU4NTY0MjU2MDIyNTI5Mg.Gz6k4y.mHc-SE0CG30uVG21SetgZcUoOmB0sXRFjREM1M"
NOTIFICATION_CHANNEL_ID = 1555602738526683267
CHECK_INTERVAL_SECONDS = 15

TARGET_USERS = {
    1342632946: {"role": "Owner"},
    571607556: {"role": "Head Admin"},
    1843844364: {"role": "Admin"},
    686731702: {"role": "Admin"},
    2010424505: {"role": "Admin"},
    96770879: {"role": "Admin"},
    409370921: {"role": "Senior Moderator"},
    839663779: {"role": "Senior Moderator"},
    470241215: {"role": "Senior Moderator"},
    212612291: {"role": "Senior Moderator"},
    854775261: {"role": "Senior Moderator"},
    1681116715: {"role": "Senior Moderator"},
    109018315: {"role": "Senior Moderator"},
    499293170: {"role": "Senior Moderator"},
    609110155: {"role": "Senior Moderator"},
    2894841464: {"role": "Senior Moderator"},
    1721395284: {"role": "Tester"},
}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

user_states = {
    uid: {"presence_type": None, "place_id": None} for uid in TARGET_USERS
}
session = None


async def fetch_user_profiles(user_ids):
  url = "https://users.roblox.com/v1/users"
  payload = {"userIds": user_ids, "excludeBannedUsers": False}
  try:
    async with session.post(url, json=payload) as resp:
      if resp.status == 200:
        data = await resp.json()
        for user in data.get("data", []):
          uid = user["id"]
          if uid in TARGET_USERS:
            TARGET_USERS[uid]["display_name"] = user.get(
                "displayName", f"User_{uid}"
            )
            TARGET_USERS[uid]["username"] = user.get("name", f"User_{uid}")
  except Exception as e:
    print(f"[ERROR] Profile fetch failed: {e}")


async def fetch_roblox_presences(user_ids):
  url = "https://presence.roblox.com/v1/presence/users"
  payload = {"userIds": user_ids}
  try:
    async with session.post(url, json=payload) as resp:
      if resp.status == 200:
        data = await resp.json()
        return data.get("userPresences", [])
  except Exception as e:
    print(f"[ERROR] Presence fetch failed: {e}")
  return []


async def fetch_game_info(place_id):
  if not place_id:
    return "Private Game / Unknown"
  url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"
  try:
    async with session.get(url) as resp:
      if resp.status == 200:
        data = await resp.json()
        universe_id = data.get("universeId")
        if universe_id:
          details_url = (
              f"https://games.roblox.com/v1/games?universeIds={universe_id}"
          )
          async with session.get(details_url) as g_resp:
            if g_resp.status == 200:
              g_data = await g_resp.json()
              games = g_data.get("data", [])
              if games:
                return games[0].get("name", "Unknown Game")
  except Exception as e:
    print(f"[ERROR] Game fetch failed: {e}")
  return f"Place ID: {place_id}"


@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def track_user_presences():
  channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
  if not channel:
    try:
      channel = await bot.fetch_channel(NOTIFICATION_CHANNEL_ID)
    except Exception:
      return

  user_ids = list(TARGET_USERS.keys())
  presences = await fetch_roblox_presences(user_ids)

  for presence in presences:
    uid = presence.get("userId")
    if uid not in TARGET_USERS:
      continue

    user_info = TARGET_USERS[uid]
    p_type = presence.get("userPresenceType", 0)
    place_id = presence.get("placeId")

    state = user_states[uid]
    prev_type = state["presence_type"]
    prev_place = state["place_id"]

    if prev_type is None:
      state["presence_type"] = p_type
      state["place_id"] = place_id
      continue

    if p_type == 2 and prev_type == 2 and not place_id and prev_place:
      continue

    has_status_changed = p_type != prev_type
    has_game_changed = (p_type == 2) and place_id and (place_id != prev_place)

    if has_status_changed or has_game_changed:
      state["presence_type"] = p_type
      state["place_id"] = place_id

      display_name = user_info.get("display_name", f"User_{uid}")
      username = user_info.get("username", f"User_{uid}")
      role = user_info.get("role", "Staff")

      emoji = "🔴"
      game_text = ""

      if p_type == 1:
        emoji = "🟢"
      elif p_type == 2:
        emoji = "🎮"
        game_title = await fetch_game_info(place_id)
        game_text = f" | Playing: **{game_title}**"
      elif p_type == 3:
        emoji = "🛠️️"
        game_text = " | **In Roblox Studio**"

      msg = (
          f"@everyone {emoji} **{role}** | {display_name} (@{username}){game_text}"
      )
      print(f"[AUTO-NOTIFY] {msg}")

      try:
        await channel.send(msg)
      except Exception as send_err:
        print(f"[ERROR] Send error: {send_err}")


@track_user_presences.before_loop
async def before_track():
  await bot.wait_until_ready()


@bot.event
async def on_ready():
  global session
  if session is None:
    session = aiohttp.ClientSession()

  print(f"[READY] Logged in as {bot.user}")
  await fetch_user_profiles(list(TARGET_USERS.keys()))

  if not track_user_presences.is_running():
    track_user_presences.start()


@bot.command(name="status")
async def status(ctx):
  user_ids = list(TARGET_USERS.keys())
  presences = await fetch_roblox_presences(user_ids)
  presence_map = {p.get("userId"): p for p in presences}

  lines = []
  for uid, info in TARGET_USERS.items():
    p = presence_map.get(uid, {})
    p_type = p.get("userPresenceType", 0)
    place_id = p.get("placeId")

    emoji = "🔴"
    game_text = ""

    if p_type == 1:
      emoji = "🟢"
    elif p_type == 2:
      emoji = "🎮"
      game_title = await fetch_game_info(place_id)
      game_text = f" (Playing: {game_title})"
    elif p_type == 3:
      emoji = "🛠️"
      game_text = " (In Studio)"

    display_name = info.get("display_name", f"User_{uid}")
    username = info.get("username", f"User_{uid}")
    role = info.get("role", "Staff")

    lines.append(f"{emoji} **{role}** | {display_name} (@{username}){game_text}")

  embed = discord.Embed(
      title="Tracked Staff Status",
      description="\n".join(lines),
      color=discord.Color.blue(),
  )
  await ctx.send(embed=embed)


bot.run(BOT_TOKEN)

