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
# vocab = ['fuck', 'bitch', 'cunt', 'shit', 'ass', 'nigger', 'nigga', 'nibba', 'faggot'] #can be configurable
# data = pd.DataFrame(columns=['content', 'time', 'author'])

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
    
# @bot.command()
# async def test(ctx, arg):
#     await ctx.send(arg)

# @bot.command()
# @commands.is_owner()
# async def scan(ctx, arg=None):
#     global data, new

#     data = pd.DataFrame(columns=['content', 'time', 'author'])

#     arg=datetime.datetime(2022, 6, 12, 0, 14, 0, 0)

#     data = pd.read_csv("data.csv")
#     data.drop('Unnamed: 0', axis=1, inplace=True)

#     await ctx.send('Scanning in progress')

#     for channel in ctx.guild.channels:
#         if isinstance(channel, discord.TextChannel):
#             async for msg in channel.history(limit=1000000, after=arg): 
#                 if(msg.content):
#                     if (msg.author.bot == False and msg.author != bot.user):                                        
#                         data = data.append({'content': msg.content,
#                                             'time': msg.created_at,
#                                             'author': msg.author.name}, ignore_index=True)   
                
#     file_location = "" # Set the string to where you want the file to be saved to
#     data.to_csv(file_location)
    
#     await ctx.send('Scan complete')
#     await ctx.send('Compiling data')

#     wordCountsPerCtx = {word: [0] * len(data.author.unique()) for word in vocab}
#     wordCountsPerCtx = pd.DataFrame(wordCountsPerCtx)

#     new = pd.concat([pd.DataFrame(data.author.unique()), wordCountsPerCtx], axis=1)
#     new.index +=1
#     new = new.rename(columns={0: "Name"})
#     new.set_index([new.index, "Name"], inplace=True)
#     data['content'] = data['content'].str.lower()

#     count = 0
#     for name in data.author.unique():
#         count += 1

#         numFuck = 0
#         numBitch = 0
#         numCunt = 0
#         numShit = 0
#         numAss = 0
#         numNr = 0
#         numNa = 0
#         numNb = 0
#         numFg = 0
#         for msg in data.loc[data['author'] == name].content:
#             #print(msg)
#             numFuck += msg.count('fuck')
#             numBitch += msg.count('bitch')
#             numCunt += msg.count('cunt')
#             numShit += msg.count('shit')
#             numAss += msg.count('ass')
#             numNr += msg.count('nigger')
#             numNa += msg.count('nigga')
#             numNb += msg.count('nibba')
#             numFg += msg.count('faggot')
#             #print(df.loc[df['author'] == name].content)
#             #print(numFuck)
#         new.loc[(count, name), 'fuck'] = numFuck
#         new.loc[(count, name), 'bitch'] = numBitch
#         new.loc[(count, name), 'cunt'] = numCunt
#         new.loc[(count, name), 'shit'] = numShit
#         new.loc[(count, name), 'ass'] = numAss
#         new.loc[(count, name), 'nigger'] = numNr
#         new.loc[(count, name), 'nigga'] = numNa
#         new.loc[(count, name), 'nibba'] = numNb
#         new.loc[(count, name), 'faggot'] = numFg

#     await ctx.send('Compilation complete')

# @bot.command()
# async def leaderboard(ctx, arg=None):
#     global data, new

#     if (arg):
#         arg = arg.lower()
#         if (arg == "breakdown"):
#             d = '```'+ new.to_string() + '```'
#             embed = discord.Embed(title = 'Leaderboard Breakdown', description = d)
#             await ctx.send(embed = embed)
#         else:
#             #index = new.columns.get_loc(arg)
#             leader = new[arg].copy()
#             leader = leader.sort_values(ascending=False)
#             leader = leader.reset_index()
#             leader.drop('level_0', axis=1, inplace=True)
#             leader.index += 1

#             d = '```'+ leader.to_string() + '```'
#             embed = discord.Embed(title = arg.capitalize() + ' Leaderboard', description = d)
#             await ctx.send(embed = embed)
#     else:
#         new['Total'] = new.sum(axis=1)
#         leader = new['Total'].copy()
#         leader = leader.sort_values(ascending=False)
#         leader = leader.reset_index()
#         leader.drop('level_0', axis=1, inplace=True)
#         leader.index += 1

#         d = '```'+ leader.to_string() + '```'
#         embed = discord.Embed(title =  'Total Swears Leaderboard', description = d)
#         await ctx.send(embed = embed)

bot.run(TOKEN)   