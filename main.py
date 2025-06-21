import os
from re import S
import discord
from discord import app_commands
import pandas as pd
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import re

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
                    'author_id': msg.author.id,
                    'author_name': msg.author.name
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

    await interaction.response.defer(thinking=True, ephemeral=True)

    try:
        await interaction.edit_original_response(content="Loading scanned data...")
        analysis_data = pd.DataFrame()
        if not data.empty:
            analysis_data = data.copy()
        else:
            try:
                print("In-memory data is empty, trying to load from data.csv...")
                analysis_data = pd.read_csv("data.csv")
                print("Successfully loaded data from data.csv")
            except FileNotFoundError:
                await interaction.edit_original_response(content='No data found. Please run `/scan` first.')
                return

        if analysis_data.empty:
            await interaction.edit_original_response(content='Scanned data is empty. Nothing to analyse.')
            return
        
        await interaction.edit_original_response(content=f"Filtering {len(analysis_data)} messages...")
        
        analysis_data['content'] = analysis_data['content'].astype(str).str.lower()
        url_mask = analysis_data['content'].str.contains(r'https?://\S+', regex=True)
        command_prefixes = ('!', '?', '.', '/', '$', '%', '^', '&', '*', '-', 's!', '>')
        command_mask = analysis_data['content'].str.strip().str.startswith(command_prefixes)
        exclude_mask = url_mask | command_mask
        filtered_data = analysis_data[~exclude_mask]
        
        await interaction.edit_original_response(content=f"Filtered down to {len(filtered_data)} messages. Starting analysis...")

        if filtered_data.empty:
            await interaction.edit_original_response(content='No valid messages remaining after filtering. Analysis complete.')
            new = pd.DataFrame(columns=vocab)
            new.index.name = "Author ID"
            new.to_csv("leaderboard_data.csv")
            return
        
        author_names = filtered_data.groupby('author_id')['author_name'].last()

        word_counts = pd.DataFrame(0, index=author_names.index, columns=vocab)
        if vocab: 
            total_words = len(vocab)
            for i, word in enumerate(vocab):
                if (i + 1) % 5 == 0 or (i + 1) == total_words:
                    progress_percent = (i + 1) / total_words * 100
                    await interaction.edit_original_response(content=f"Analysing word counts: [{i+1}/{total_words}] ({progress_percent:.1f}%)")
                word_counts[word] = filtered_data.groupby('author_id')['content'].apply(lambda x: x.str.count(r'\b' + re.escape(word) + r'\b').sum())

        await interaction.edit_original_response(content="Calculating totals and percentages...")
        
        total_messages = filtered_data.groupby('author_id').size().rename('Total Messages')
        total_words = filtered_data.groupby('author_id')['content'].apply(lambda x: x.str.split().str.len().sum()).rename('Total Words')
        total_swears = word_counts.sum(axis=1).rename('Total Swears')

        new = pd.concat([author_names, word_counts, total_messages, total_words, total_swears], axis=1)
        new.fillna(0, inplace=True)
        
        new['Swear Percentage'] = (new['Total Swears'] / (new['Total Words'] + 1e-9) * 100).fillna(0)

        count_cols = vocab + ['Total Messages', 'Total Words', 'Total Swears']
        for col in count_cols:
            if col in new.columns:
                new[col] = new[col].astype(int)
        
        new.index.name = "Author ID"
        leaderboard_cache_file = "leaderboard_data.csv"
        new.to_csv(leaderboard_cache_file)
        
        await interaction.edit_original_response(content='Analysis complete. Leaderboard is now up to date.')

    except Exception as e:
        print(f"An error occurred during analysis: {e}")
        if not interaction.is_response_sent():
            await interaction.edit_original_response(content=f"An unexpected error occurred during analysis. Please check the console.")

@analyse.error
async def on_analyse_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message('You must be the bot owner to use this command.', ephemeral=True)

@scan.error
async def on_scan_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message('You must be the bot owner to use this command.', ephemeral=True)

@bot.tree.command(name="leaderboard")
@app_commands.describe(arg="The category for the leaderboard (e.g., a specific word, user name/mention, 'breakdown', 'percentage', or leave empty for total).")
async def leaderboard(interaction: discord.Interaction, arg: str = None):
    global new

    if new.empty:
        try:
            print("In-memory leaderboard is empty, loading from cache...")
            new = pd.read_csv("leaderboard_data.csv", index_col="Author ID")
            print("Successfully loaded leaderboard data from cache.")
        except FileNotFoundError:
            await interaction.response.send_message('No analysed data found. Please run `/analyse` first.', ephemeral=True)
            return
        except Exception as e:
            print(f"Error loading leaderboard cache: {e}")
            await interaction.response.send_message('Could not load leaderboard data. Please run `/analyse` again.', ephemeral=True)
            return

    # Total Leaderboard 
    if not arg:
        total_leaderboard = new[vocab].sum(axis=1).sort_values(ascending=False)
        total_leaderboard = total_leaderboard[total_leaderboard > 0]
        
        if total_leaderboard.empty:
            await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
            return

        embed = discord.Embed(title="Total Swears Leaderboard", color=discord.Color.blue())
        for user_id, total in total_leaderboard.head(25).items():
            name = new.loc[user_id, 'author_name']
            embed.add_field(name=f"#{len(embed.fields) + 1} {name}", value=f"**{int(total)}** total swears", inline=False)
        await interaction.response.send_message(embed=embed)
        return

    arg_lower = arg.lower()

    if arg_lower == "breakdown":
        display_df = new.copy()
        display_df = display_df.loc[:, (display_df != 0).any(axis=0)]
        if display_df.empty or not vocab:
            await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
            return
        display_df['Total'] = display_df[vocab].sum(axis=1)
        display_df.sort_values(by='Total', ascending=False, inplace=True)
        display_df = display_df[display_df['Total'] > 0]
        if display_df.empty:
            await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
            return
        embed = discord.Embed(title="Leaderboard Breakdown", description="Top users and their most used words.", color=discord.Color.purple())
        for user_id, row in display_df.head(10).iterrows():
            name = row['author_name']
            total = int(row['Total'])
            user_words = row[vocab].sort_values(ascending=False)
            top_words = user_words[user_words > 0]
            breakdown_text = "\n".join([f"- {word}: **{int(count)}**" for word, count in top_words.items()]) if not top_words.empty else "No specific tracked words used."
            embed.add_field(name=f"{name} (Total: {total})", value=breakdown_text, inline=False)
        await interaction.response.send_message(embed=embed)
        return

    if arg_lower == "percentage":
        if 'Swear Percentage' not in new.columns:
            await interaction.response.send_message("Percentage data not available. Please run `/analyse` again.", ephemeral=True)
            return
        leader = new[['author_name', 'Swear Percentage', 'Total Swears', 'Total Words']].copy().sort_values(by='Swear Percentage', ascending=False)
        leader = leader[leader['Swear Percentage'] > 0]
        if leader.empty:
            await interaction.response.send_message("No one has a swear percentage yet.", ephemeral=True)
            return
        embed = discord.Embed(title="Swear-to-Word Ratio Leaderboard", description="Percentage of total words that are tracked swears.", color=discord.Color.orange())
        for _, row in leader.head(25).iterrows():
            name = row['author_name']
            percentage = row['Swear Percentage']
            swear_count = int(row['Total Swears'])
            total_word_count = int(row['Total Words'])
            embed.add_field(name=f"#{len(embed.fields) + 1} {name}", value=f"**{percentage:.2f}%** ({swear_count} swears / {total_word_count} words)", inline=False)
        await interaction.response.send_message(embed=embed)
        return

    if arg_lower in vocab:
        leader = new[['author_name', arg_lower]].copy().sort_values(by=arg_lower, ascending=False)
        leader = leader[leader[arg_lower] > 0]
        if leader.empty:
            await interaction.response.send_message(f"No one has said '{arg}' yet.", ephemeral=True)
            return
        embed = discord.Embed(title=f"{arg.capitalize()} Leaderboard", color=discord.Color.green())
        for _, row in leader.head(25).iterrows():
            name = row['author_name']
            count = int(row[arg_lower])
            embed.add_field(name=f"#{len(embed.fields) + 1} {name}", value=f"**{count}** times", inline=False)
        await interaction.response.send_message(embed=embed)
        return

    user_data = None
    # Check for mention or raw ID
    match = re.match(r'<@!?(\d+)>$', arg)
    user_id_to_find = int(match.group(1)) if match else (int(arg) if arg.isdigit() else None)
    if user_id_to_find:
        if user_id_to_find in new.index:
            user_data = new.loc[user_id_to_find]
    else:
        results = new[new['author_name'].str.lower() == arg_lower]
        if not results.empty:
            user_data = results.iloc[0]

    if user_data is not None:
        user_name = user_data['author_name']
        total_swears = int(user_data.get('Total Swears', 0))
        total_words = int(user_data.get('Total Words', 0))
        percentage = user_data.get('Swear Percentage', 0.0)
        user_word_counts = user_data[vocab].sort_values(ascending=False)
        user_word_counts = user_word_counts[user_word_counts > 0]
        
        embed = discord.Embed(title=f"Stats for {user_name}", color=discord.Color.teal())
        embed.add_field(name="Total Swears", value=f"**{total_swears}**", inline=True)
        embed.add_field(name="Total Words", value=f"**{total_words}**", inline=True)
        embed.add_field(name="Swear Ratio", value=f"**{percentage:.2f}%**", inline=True)
        if not user_word_counts.empty:
            breakdown_text = "\n".join([f"- {word}: **{int(count)}**" for word, count in user_word_counts.items()])
            embed.add_field(name="Word Breakdown", value=breakdown_text, inline=False)
        else:
            embed.add_field(name="Word Breakdown", value="No tracked words used.", inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"Sorry, '{arg}' is not a valid category or user.", ephemeral=True)

bot.run(TOKEN)