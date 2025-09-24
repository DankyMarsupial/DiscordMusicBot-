from typing import Final
import os
from dotenv import load_dotenv
import discord
from discord import Intents, Client, Message, BotIntegration
from responses import get_response
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from discord.opus import load_opus
from queue import Queue


load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables")



intents: Intents = Intents.default()
intents.message_content = True #NOQA

# Define bot command prefix
bot = commands.Bot(command_prefix='!', intents=intents)

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# Dictionary to keep track of voice clients per guild
voice_clients = {}
queues = {}

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

yt_urls = Queue(maxsize=0)
vc: any
guild_id: any

@bot.command(name='play', help='Play audio from a URL')
async def play(ctx, url: str):
    # Check if user is in a voice channel
    if not ctx.author.voice:
        await ctx.send('You need to be in a voice channel to use this command.')
        return
    guild_id = ctx.guild.id

    # Initialize queue for the guild if it doesn't exist
    if guild_id not in queues:
        queues[guild_id] = Queue()

    # Add URL to the queue
    queues[guild_id].put(url)
    await ctx.send(f'Link Added to Queue at Position {queues[guild_id].qsize()}')

    # Get the user's voice channel
    voice_channel = ctx.message.author.voice.channel
    

    # Connect to the user's voice channel
    if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
        voice_clients[guild_id] = await voice_channel.connect()
    
    # Start playing if not already playing
    if not voice_clients[guild_id].is_playing():
        await bckgrnd_Play(ctx)

async def bckgrnd_Play(ctx):
    guild_id = ctx.guild.id
    vc = voice_clients[guild_id]

    while not queues[guild_id].empty():
        url = queues[guild_id].get()
        
        # Download the audio
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                mp3_file = filename.rsplit('.', 1)[0] + '.mp3'
        except youtube_dl.utils.DownloadError as e:
            print(f"Error downloading video: {e}")
            await ctx.send("Error downloading the video. Please try again later.")
            return

        try:
            # Play the audio
            await ctx.send(f"Now playing: {info['title']}")
            vc.play(discord.FFmpegPCMAudio(mp3_file), after=lambda e: asyncio.run_coroutine_threadsafe(bckgrnd_Play(ctx), bot.loop))
            vc.source = discord.PCMVolumeTransformer(vc.source)
            vc.source.volume = 0.6
        except discord.Forbidden:
            await ctx.send('Bot does not have permission to speak in this voice channel.')
            return

    # Disconnect after playing all songs in the queue
    if not vc.is_playing() and queues[guild_id].empty():
        print("Queue empty, disconnecting...")
        await vc.disconnect()
        del voice_clients[guild_id]
        del queues[guild_id]


async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(message was empty because intents were not enabled probably)')
        return

    is_private = user_message[0] == '?'
    if is_private :
        user_message = user_message[1:]

    try: 
        response: str = get_response(user_message)
        if is_private:
            await message.author.send(response)
        else:
            await message.channel.send(response)

    except Exception as e:
        print(e)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return
    
    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)

    print(f'[{channel}] {username}: "{user_message}"')
    await bot.process_commands(message)


def main() -> None:
    #if not discord.opus.is_loaded():
       #load_opus("opus-1.5.2")
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
