import os
from re import S
import discord
from discord import app_commands
import pandas as pd
import numpy as py
import datetime
from discord.ext import commands
from dotenv import load_dotenv

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

@bot.tree.command(name="hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hey {interaction.user.mention}! This is a slash command!", ephemeral=True)
    
@bot.tree.command(name="say")
@app_commands.describe(thing_to_say = "What should the bot say?")
async def say(interaction: discord.Interaction, thing_to_say: str):
    await interaction.response.send_message(f"{interaction.user.name} said `{thing_to_say}`")

@bot.tree.command(name="scan", description="Scans all messages in the server and counts word usage.")
@app_commands.checks.is_owner()
async def scan(interaction: discord.Interaction):
    global data, new

    await interaction.response.defer(thinking=True)
    await interaction.followup.send('Scanning in progress...')

    all_messages = []
    for channel in interaction.guild.text_channels:
        async for msg in channel.history(limit=None): 
            if msg.content and not msg.author.bot:
                all_messages.append({
                    'content': msg.content,
                    'time': msg.created_at,
                    'author': msg.author.name
                })
    
    if not all_messages:
        await interaction.followup.send('No messages found to analyse.')
        return

    data = pd.DataFrame(all_messages)
                
    file_location = "data.csv"
    data.to_csv(file_location)
    
    await interaction.followup.send('Scan complete')
    await interaction.followup.send('Compiling data')

    unique_authors = data.author.unique()
    wordCountsPerCtx = {word: [0] * len(unique_authors) for word in vocab}
    wordCountsPerCtx = pd.DataFrame(wordCountsPerCtx)

    new = pd.concat([pd.DataFrame(unique_authors, columns=["Name"]), wordCountsPerCtx], axis=1)
    new.index +=1
    new.set_index([new.index, "Name"], inplace=True)
    data['content'] = data['content'].str.lower()

    for i, name in enumerate(unique_authors):
        user_messages = data.loc[data['author'] == name, 'content']
        for word in vocab:
            total_count = user_messages.str.count(word).sum()
            new.loc[(i + 1, name), word] = total_count

    await interaction.followup.send('Compilation complete')

@scan.error
async def on_scan_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message('You must be the bot owner to use this command.', ephemeral=True)

@bot.tree.command(name="leaderboard")
@app_commands.describe(arg="The category for the leaderboard (e.g., a specific word, 'breakdown', or leave empty for total).")
async def leaderboard(interaction: discord.Interaction, arg: str = None):
    global data, new

    if (arg):
        arg = arg.lower()
        if (arg == "breakdown"):
            d = '```'+ new.to_string() + '```'
            embed = discord.Embed(title = 'Leaderboard Breakdown', description = d)
            await interaction.response.send_message(embed = embed)
        else:
            #index = new.columns.get_loc(arg)
            leader = new[arg].copy()
            leader = leader.sort_values(ascending=False)
            leader = leader.reset_index()
            leader.drop('level_0', axis=1, inplace=True)
            leader.index += 1

            d = '```'+ leader.to_string() + '```'
            embed = discord.Embed(title = arg.capitalize() + ' Leaderboard', description = d)
            await interaction.response.send_message(embed = embed)
    else:
        new['Total'] = new.sum(axis=1)
        leader = new['Total'].copy()
        leader = leader.sort_values(ascending=False)
        leader = leader.reset_index()
        leader.drop('level_0', axis=1, inplace=True)
        leader.index += 1

        d = '```'+ leader.to_string() + '```'
        embed = discord.Embed(title =  'Total Swears Leaderboard', description = d)
        await interaction.response.send_message(embed = embed)

bot.run(TOKEN)   