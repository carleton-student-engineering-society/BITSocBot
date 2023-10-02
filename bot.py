import nextcord
from nextcord.ext import commands
import mysql.connector
import requests
import re
from settings import *

connection = mysql.connector.connect(host=DB_HOST,
                                     database=DB_NAME,
                                     user=DB_USER,
                                     password=DB_PASS)

cursor = connection.cursor(prepared=True)

bot = commands.Bot()

CLEANR = re.compile('<.*?>') 

def cleanhtml(raw_html):
    cleantext = re.sub(CLEANR, '', raw_html)
    return cleantext.replace('\n', '')

@bot.slash_command(description="Verifies your account and gives you access to the server!")
async def verify(i, full_name: str, student_number: int):
    await i.response.defer()
    r = requests.get(ID_URL + str(student_number))
    if r.status_code != 200:
        await i.send("An error occurred! Error 1", ephemeral=True)
        return
    id_name = cleanhtml(r.text)
    query = "SELECT * FROM banned WHERE stud_id=%s;"
    cursor.execute(query, (student_number,))
    user = cursor.fetchone()
    if user is not None:
        await i.send("Error: You have been banned from this server!", ephemeral=True)
        channel = i.guild.get_channel(INFO_CHANNEL)
        await channel.send("Warning: User (" + i.user.mention + " - " + id_name + ") tried to join but they are banned!")
        return
    query = "SELECT * FROM users WHERE discord_id=%s OR stud_id=%s;"
    cursor.execute(query, (i.user.id,student_number))
    user = cursor.fetchone()
    if user is not None:
        await i.send("Error: You have already joined this server!", ephemeral=True)
        channel = i.guild.get_channel(INFO_CHANNEL)
        await channel.send("Warning: User (" + i.user.mention + " - " + id_name + ") tried to join multiple times!")
        return
    if id_name.lower() == full_name.lower():
        member = i.user
        role = i.guild.get_role(VERIFIED_ROLE)
        await member.add_roles(role, reason=id_name)
        query = """INSERT INTO users (discord_id, stud_id) VALUES (%s,%s);"""
        data = (member.id, student_number)
        cursor.execute(query, data)
        connection.commit()
        await i.send("Successfully verified!", ephemeral=True)
        return
    else:
        channel = i.guild.get_channel(INFO_CHANNEL)
        await channel.send("Warning: User (" + i.user.mention + " - " + id_name + " - " + full_name +") failed to verify, please manually review!")
        await i.send("Failed to verify, moderators have been notified and will manually approve", ephemeral=True)
        return


@bot.event
async def on_ready():
    print('Ready!')

@bot.event
async def on_error(event):
    channel = i.guild.get_channel(INFO_CHANNEL)
    await channel.send("An error occurred!!!\n" + event)

@bot.event
async def on_member_ban(guild, user):
    channel = guild.get_channel(INFO_CHANNEL)
    query = "SELECT stud_id FROM users WHERE discord_id=%s;"
    cursor.execute(query, (user.id,))
    u = cursor.fetchone()
    if u is None:
        await channel.send("Warning: User (" + user.mention + ") was banned but no matching student id was found!")
        return
    stud_id = u[0]
    query = """INSERT INTO banned (stud_id) VALUES (%s);"""
    data = (stud_id,)
    cursor.execute(query, data)
    connection.commit()
    await channel.send("Info: User (" + user.mention + ") was banned!")

@bot.event
async def on_member_unban(guild, user):
    channel = guild.get_channel(INFO_CHANNEL)
    query = "SELECT stud_id FROM users WHERE discord_id=%s;"
    cursor.execute(query, (user.id,))
    u = cursor.fetchone()
    if u is None:
        await channel.send("Warning: User (" + user.mention + ") was banned but no matching student id was found!")
        return
    stud_id = u[0]
    query = """DELETE FROM banned WHERE stud_id=%s;"""
    data = (stud_id,)
    cursor.execute(query, data)
    connection.commit()
    await channel.send("Info: User (" + user.mention + ") was unbanned!")

bot.run(TOKEN)
