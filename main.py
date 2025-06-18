import os
from re import S
import discord
from discord import app_commands
import pandas as pd
import numpy as py
import datetime
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
bot = commands.Bot(command_prefix='s!', intents = discord.Intents.all())

def load_swear_words(filename="profanity.txt"):
    """Loads swear words from a file, one word per line."""
    try:
        with open(filename, "r") as f:
            words = [line.strip().lower() for line in f if line.strip()]
            print(f"Loaded {len(words)} words from {filename}.")
            return words
    except FileNotFoundError:
        print(f"Warning: '{filename}' not found.")

vocab = load_swear_words()
data = pd.DataFrame(columns=['content', 'time', 'author'])
new = pd.DataFrame()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

    try:
        synced = await bot.tree.sync()
        print(f"synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

async def scan_channel(channel: discord.TextChannel):
    """Scans a single channel and returns a list of message data."""
    messages = []
    try:
        async for msg in channel.history(limit=None):
            if msg.content and not msg.author.bot:
                messages.append({
                    'content': msg.content,
                    'time': msg.created_at,
                    'author': msg.author.name
                })
        print(f"Finished scan for #{channel.name}. Found {len(messages)} messages.")
        return messages
    except discord.errors.Forbidden:
        print(f"Skipping channel #{channel.name} due to missing permissions.")
        return []
    except Exception as e:
        print(f"An error occurred in channel #{channel.name}: {e}")
        return []

@bot.tree.command(name="hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hey {interaction.user.mention}! This is a slash command!", ephemeral=True)
    
@bot.tree.command(name="say")
@app_commands.describe(thing_to_say = "What should the bot say?")
async def say(interaction: discord.Interaction, thing_to_say: str):
    await interaction.response.send_message(f"{interaction.user.name} said `{thing_to_say}`")

@bot.tree.command(name="scan", description="Scans all messages in the server and saves them for analysis.")
@app_commands.check(lambda interaction: bot.is_owner(interaction.user))
async def scan(interaction: discord.Interaction):
    """Scans all text channels and saves messages to a CSV file."""
    global data

    await interaction.response.defer(thinking=True, ephemeral=True)
    
    text_channels = interaction.guild.text_channels
    print(f"Creating scan tasks for {len(text_channels)} channels.")

    tasks = [scan_channel(channel) for channel in text_channels]
    list_of_message_lists = await asyncio.gather(*tasks)

    print("\nAll channel scans complete. Aggregating results.")
    all_messages = [message for sublist in list_of_message_lists for message in sublist]

    if not all_messages:
        await interaction.followup.send('No messages found to scan.', ephemeral=True)
        print("Scan resulted in no data.")
        return

    data = pd.DataFrame(all_messages)
    file_location = "data.csv"
    data.to_csv(file_location, index=False)
    
    print(f"Scan complete. Found {len(all_messages)} messages and saved to {file_location}.")
    await interaction.followup.send(f'Scan complete. Found {len(all_messages)} messages. Run `/analyse` to process them.', ephemeral=True)

@bot.tree.command(name="analyse", description="Analyses the previously scanned messages to generate leaderboards.")
@app_commands.check(lambda interaction: bot.is_owner(interaction.user))
async def analyse(interaction: discord.Interaction):
    """Processes the scanned data to count word usage per user and caches the result."""
    global data, new

    if data.empty:
        try:
            print("In-memory data is empty, trying to load from data.csv...")
            data = pd.read_csv("data.csv")
            print("Successfully loaded data from data.csv")
        except FileNotFoundError:
            await interaction.response.send_message('No data found. Please run `/scan` first.', ephemeral=True)
            return
    
    await interaction.response.defer(thinking=True, ephemeral=True)

    unique_authors = data.author.unique()
    # Initialize DataFrame with authors as index and words as columns
    new = pd.DataFrame(0, index=unique_authors, columns=vocab)
    new.index.name = "Name"
    
    data['content'] = data['content'].astype(str).str.lower()

    print("Compiling user statistics...")
    for name in unique_authors:
        user_messages = data.loc[data['author'] == name, 'content']
        for word in vocab:
            total_count = user_messages.str.count(word).sum()
            new.loc[name, word] = total_count

    # Cache the results to a CSV file
    leaderboard_cache_file = "leaderboard_data.csv"
    new.to_csv(leaderboard_cache_file)
    
    print(f"Analysis complete. Leaderboard data saved to {leaderboard_cache_file}.")
    await interaction.followup.send('Analysis complete. Leaderboard is now up to date.', ephemeral=True)

@analyse.error
async def on_analyse_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message('You must be the bot owner to use this command.', ephemeral=True)

@scan.error
async def on_scan_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message('You must be the bot owner to use this command.', ephemeral=True)

@bot.tree.command(name="leaderboard")
@app_commands.describe(arg="The category for the leaderboard (e.g., a specific word, 'breakdown', or leave empty for total).")
async def leaderboard(interaction: discord.Interaction, arg: str = None):
    global new

    # If 'new' dataframe is empty, try to load from the cache file.
    if new.empty:
        try:
            print("In-memory leaderboard is empty, loading from cache...")
            new = pd.read_csv("leaderboard_data.csv", index_col="Name")
            print("Successfully loaded leaderboard data from cache.")
        except FileNotFoundError:
            await interaction.response.send_message('No analysed data found. Please run `/analyse` first.', ephemeral=True)
            return
        except Exception as e:
            print(f"Error loading leaderboard cache: {e}")
            await interaction.response.send_message('Could not load leaderboard data. Please run `/analyse` again.', ephemeral=True)
            return

    if arg:
        arg = arg.lower()
        if arg == "breakdown":
            # Create a copy for display to avoid modifying the global 'new' DataFrame
            display_df = new.copy()
            display_df['Total'] = display_df.sum(axis=1)
            display_df.sort_values(by='Total', ascending=False, inplace=True)
            d = '```'+ display_df.to_string() + '```'
            embed = discord.Embed(title='Leaderboard Breakdown', description=d)
            await interaction.response.send_message(embed=embed)
        else:
            if arg not in new.columns:
                await interaction.response.send_message(f"Sorry, '{arg}' is not a tracked word.", ephemeral=True)
                return
            
            # Create a leaderboard for the specific word
            leader = new[[arg]].copy().sort_values(by=arg, ascending=False)
            leader = leader[leader[arg] > 0] # Only show users with a count > 0
            leader = leader.reset_index()
            leader.index += 1

            d = '```'+ leader.to_string() + '```'
            embed = discord.Embed(title=f'{arg.capitalize()} Leaderboard', description=d)
            await interaction.response.send_message(embed=embed)
    else:
        # Create a total leaderboard
        # Calculate total on a copy to avoid modifying the global 'new' DataFrame
        total_leaderboard = new.sum(axis=1).sort_values(ascending=False)
        total_leaderboard = total_leaderboard[total_leaderboard > 0] # Only show users with a count > 0
        leader = total_leaderboard.reset_index(name='Total')
        leader.index += 1

        d = '```'+ leader.to_string() + '```'
        embed = discord.Embed(title='Total Swears Leaderboard', description=d)
        await interaction.response.send_message(embed=embed)

bot.run(TOKEN)