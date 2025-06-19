import os
from re import S
import discord
from discord import app_commands
import pandas as pd
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

    analysis_data = pd.DataFrame()
    if not data.empty:
        analysis_data = data.copy()
    else:
        try:
            print("In-memory data is empty, trying to load from data.csv...")
            analysis_data = pd.read_csv("data.csv")
            print("Successfully loaded data from data.csv")
        except FileNotFoundError:
            await interaction.response.send_message('No data found. Please run `/scan` first.', ephemeral=True)
            return

    if analysis_data.empty:
        await interaction.response.send_message('Scanned data is empty. Nothing to analyse.', ephemeral=True)
        return
    
    await interaction.response.defer(thinking=True, ephemeral=True)

    # --- Filtering Logic ---
    print(f"Starting analysis on {len(analysis_data)} messages.")
    analysis_data['content'] = analysis_data['content'].astype(str).str.lower()

    # Create a mask to identify and exclude messages containing URLs.
    url_mask = analysis_data['content'].str.contains(r'https?://\S+', regex=True)

    # Create a mask to identify and exclude messages that are likely bot commands.
    command_prefixes = ('!', '?', '.', '/', '$', '%', '^', '&', '*', '-', 's!', '>')
    command_mask = analysis_data['content'].str.strip().str.startswith(command_prefixes)

    # Combine masks to find all messages that should be excluded.
    exclude_mask = url_mask | command_mask
    
    # Apply the filter to get the final, clean dataset for analysis.
    filtered_data = analysis_data[~exclude_mask]
    
    print(f"Filtered out {exclude_mask.sum()} messages (URLs or commands). Analysing {len(filtered_data)} messages.")

    if filtered_data.empty:
        await interaction.followup.send('No valid messages remaining after filtering. Analysis complete.', ephemeral=True)
        new = pd.DataFrame(columns=vocab)
        new.index.name = "Name"
        new.to_csv("leaderboard_data.csv")
        return

    unique_authors = filtered_data.author.unique()
    new = pd.DataFrame(0, index=unique_authors, columns=vocab)
    new.index.name = "Name"
    
    print("Compiling user statistics...")
    for name, group in filtered_data.groupby('author'):
        for word in vocab:
            total_count = group['content'].str.count(word).sum()
            new.loc[name, word] = total_count

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
            # Exclude columns that are all zeros
            display_df = display_df.loc[:, (display_df != 0).any(axis=0)]

            if display_df.empty:
                await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
                return

            display_df['Total'] = display_df.sum(axis=1)
            display_df.sort_values(by='Total', ascending=False, inplace=True)
            display_df = display_df[display_df['Total'] > 0]

            if display_df.empty:
                await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
                return

            embed = discord.Embed(title="Leaderboard Breakdown", description="Top users and their most used words.", color=discord.Color.purple())

            # Limit to top 10 users for a cleaner look and to avoid hitting limits
            for name, row in display_df.head(10).iterrows():
                total = int(row['Total'])
                
                user_words = row.drop('Total').sort_values(ascending=False)
                top_words = user_words[user_words > 0]
                
                if not top_words.empty:
                    breakdown_text = "\n".join([f"- {word}: **{int(count)}**" for word, count in top_words.items()])
                else:
                    breakdown_text = "No specific tracked words used."

                embed.add_field(
                    name=f"{name} (Total: {total})",
                    value=breakdown_text,
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
        else:
            if arg not in new.columns:
                await interaction.response.send_message(f"Sorry, '{arg}' is not a tracked word.", ephemeral=True)
                return
            
            # Create a leaderboard for the specific word
            leader = new[[arg]].copy().sort_values(by=arg, ascending=False)
            leader = leader[leader[arg] > 0] # Only show users with a count > 0

            if leader.empty:
                await interaction.response.send_message(f"No one has said '{arg}' yet.", ephemeral=True)
                return

            embed = discord.Embed(title=f"{arg.capitalize()} Leaderboard", color=discord.Color.green())
            # Limit to top 25 to avoid embed field limit
            for rank, (name, row) in enumerate(leader.head(25).iterrows(), 1):
                count = int(row[arg])
                embed.add_field(name=f"#{rank} {name}", value=f"**{count}** times", inline=False)

            await interaction.response.send_message(embed=embed)
    else:
        # Create a total leaderboard
        total_leaderboard = new.sum(axis=1).sort_values(ascending=False)
        total_leaderboard = total_leaderboard[total_leaderboard > 0] # Only show users with a count > 0
        
        if total_leaderboard.empty:
            await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
            return

        embed = discord.Embed(title="Total Swears Leaderboard", color=discord.Color.blue())
        # Limit to top 25 to avoid embed field limit
        for rank, (name, total) in enumerate(total_leaderboard.head(25).items(), 1):
            embed.add_field(name=f"#{rank} {name}", value=f"**{int(total)}** total swears", inline=False)

        await interaction.response.send_message(embed=embed)

bot.run(TOKEN)