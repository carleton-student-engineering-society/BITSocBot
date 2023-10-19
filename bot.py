from nextcord.ext import commands, application_checks
from nextcord import Member
import mysql.connector
import hashlib
import boto3
from settings import *

connection = mysql.connector.connect(host=DB_HOST,
                                     database=DB_NAME,
                                     user=DB_USER,
                                     password=DB_PASS)

cursor = connection.cursor(prepared=True)

ses_client = boto3.client('ses', region_name="ca-central-1", aws_access_key_id=SES_PUB, aws_secret_access_key=SES_PRIV)

bot = commands.Bot()

@bot.slash_command(description="Verifies all members!")
@application_checks.has_permissions(manage_messages=True)
async def verify_all(i):
    i.response.defer()
    role = i.guild.get_role(VERIFIED_ROLE)
    async for member in i.guild.fetch_members(limit=None):
        await member.add_roles(role)
    await i.send("Verified all members!", ephemeral=True)

@bot.slash_command(description="Gets a member's CMail")
@application_checks.has_permissions(manage_messages=True)
async def get_email(i, member: Member):
    query = """SELECT cmail FROM users WHERE discord_id=%s;"""
    data = (member.id,)
    cursor.execute(query, data)
    data = cursor.fetchone()
    if data is None:
        await i.send("No CMail address found!", ephemeral=True)
    else:
        await i.send("CMail: " + data, ephemeral=True)

@bot.slash_command(description="Verifies your account and gives you access to the server!")
async def verify(i, cmail: str):
    await i.response.defer()
    if not cmail.endswith("@cmail.carleton.ca"):
        await i.send("Error: You must use a Carleton University email address!", ephemeral=True)
        return
    query = "SELECT * FROM banned WHERE cmail=%s;"
    cursor.execute(query, (cmail,))
    user = cursor.fetchone()
    if user is not None:
        await i.send("Error: You have been banned from this server!", ephemeral=True)
        channel = i.guild.get_channel(INFO_CHANNEL)
        await channel.send("Warning: User (" + i.user.mention + " - " + cmail + ") tried to join but they are banned!")
        return
    query = "SELECT * FROM users WHERE discord_id=%s OR cmail=%s;"
    cursor.execute(query, (i.user.id,cmail))
    user = cursor.fetchone()
    if user is not None:
        await i.send("Error: You have already joined this server!", ephemeral=True)
        channel = i.guild.get_channel(INFO_CHANNEL)
        await channel.send("Warning: User (" + i.user.mention + " - " + cmail + ") tried to join multiple times!")
        return
    m = hashlib.sha256()
    hstr = HASH_PREFIX + cmail
    m.update(hstr.encode('utf-8'))
    h = m.hexdigest()[0:8]
    message = "Your verification code is: " + h
    send_args = {
            'Source': FROM,
            'Destination': {
                'ToAddresses': [
                    cmail,
                ],
            },
            'Message': {
                'Subject': {'Data': "Discord Verification Code"},
                'Body': {'Text': {'Data': message}, 'Html': {'Data': message}}}}
    ses_client.send_email(**send_args)
    await i.send("A verification code has been sent to your email. It will be in your spam folder." +
                 "Use `/verify_complete <cmail> <code>` to become verified!", ephemeral=True)

@bot.slash_command(description="Verifies your account and gives you access to the server!")
async def verify_complete(i, cmail: str, code: str):
    m = hashlib.sha256()
    hstr = HASH_PREFIX + cmail
    m.update(hstr.encode('utf-8'))
    h = m.hexdigest()[0:8]
    if h.lower() == code.lower():
        member = i.user
        role = i.guild.get_role(VERIFIED_ROLE)
        await member.add_roles(role, reason=cmail)
        query = """INSERT INTO users (discord_id, cmail) VALUES (%s,%s);"""
        data = (member.id, cmail)
        cursor.execute(query, data)
        connection.commit()
        await i.send("Successfully verified!", ephemeral=True)
        return
    else:
        channel = i.guild.get_channel(INFO_CHANNEL)
        await channel.send("Warning: User (" + i.user.mention + " - " + cmail +") failed to verify, please manually review!")
        await i.send("Failed to verify, moderators have been notified and will manually approve", ephemeral=True)
        return


@bot.event
async def on_ready():
    print('Ready!')

@bot.event
async def on_error(event):
    channel = event.guild.get_channel(INFO_CHANNEL)
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
