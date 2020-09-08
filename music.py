import discord
from discord.ext import commands
import urllib.request
import urllib.parse
import youtube_dl
import re
import asyncio
import random
import time
# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0', # bind to ipv4 since ipv6 addresses cause issues sometimes
    'simulate': True,
    'ignoreerrors': True,
    'cookiefile' : 'cookies.txt',
    'username' : 'ravi.twitch@gmail.com',
    'password' : 'idek1290'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return data['webpage_url'], cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options, before_options = " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"), data=data)
    
    @classmethod
    async def addplaylist(cls, url, person, loop, ctx):
        msg = await ctx.send(embed = discord.Embed(description="Downloading", color=0x51719f))
        info_dict = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=True))
        if info_dict['_type'] != 'playlist' or 'entries' not in info_dict:
            raise NoPlaylistException('Not a Playlist')
        f = open(person, "a+", encoding='utf8')
        x = 0
        y = 0
        await msg.edit(embed = discord.Embed(description="Adding", color=0x51719f))
        for entry in info_dict['entries']:
            x+=1
            try:
                if entry['duration'] > 60 and entry['duration'] < 1200:
                    tempurl = 'https://www.youtube.com/watch?v=' + entry['id']
                    url, templayer = await YTDLSource.from_url(tempurl, loop=loop, stream=True)
                    f.write(tempurl + "\n" + templayer.title + "\n")
                    del templayer
                    await msg.edit(embed = discord.Embed(description=f"{entry['title']} added", color=0x51719f))
                    y+=1
                else:
                    await msg.edit(embed = discord.Embed(description=f"{entry['title']} is too long/short", color=0x51719f))
                await asyncio.sleep(1)
            except:
                await msg.edit(embed = discord.Embed(description=f"Number {x} not added", color=0x51719f))
                await asyncio.sleep(1)
        await msg.delete()
        msg = await ctx.send(embed = discord.Embed(description=f"{y} songs added to playlist", color=0x51719f))
        await asyncio.sleep(5)
        await msg.delete()
        f.close()

class Queue:
    def __init__(self):
        self.playerqueue = []
        self.ctxqueue = []
        self.urlqueue = []
    
    def isEmpty(self):
        return self.playerqueue == []
    
    async def enqueue(self, ctx, player, url):
        self.playerqueue.append(player)
        self.ctxqueue.append(ctx)
        self.urlqueue.append(url)

    async def dequeue(self):
        temp = self.isEmpty()
        if not temp:
            self.ctxqueue.pop(0)
            self.urlqueue.pop(0)
            self.playerqueue.pop(0)
    
    async def zeroqueue(self, ctx, player, url):
        self.playerqueue.insert(0, player)
        self.ctxqueue.insert(0, ctx)
        self.urlqueue.insert(0, url)
    
    def currentplayer(self):
        return self.playerqueue[0]
    
    def currentctx(self):
        return self.ctxqueue[0]
        
    def currenturl(self):
        return self.urlqueue[0]
    
    def getplayer(self, x):
        return self.playerqueue[x]
    
    def getctx(self, x):
        return self.ctxqueue[x]
        
    def geturl(self, x):
        return self.urlqueue[x]
    
    def size(self):
        return len(self.urlqueue)









class MusicCog(commands.Cog, name="Music Commands"):
    
    def __init__(self, bot):
        self.bot = bot
        self.mq = Queue()
        self.playing = False
        self.ctx = 0
        self.skip = True
        self.paused = False
        self.channel = bot.get_channel(676288007556300830)
        self.guildid = bot.get_guild(218751753179365376)
        self.hyit = False
        self.playlist = "autoplaylist.txt"
        self.dlnum = 0
        self.dlqueue = [0]
        self.dlnum2 = 0
        self.starttime = 0
    
    async def dlq(self, num):
        while self.dlqueue[1] != num:
            await asyncio.sleep(2)
    
    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        self.dlnum2 = 1
        """http://discordpy.readthedocs.io/en/rewrite/api.html#discord.on_ready"""
        print(f'\n\nLogged in as: {self.bot.user.name} - {self.bot.user.id}\nVersion: {discord.__version__}\n')
        # Changes our bots Playing Status. type=1(streaming) for a standard game you could remove type and url.
        await self.bot.change_presence(activity=discord.Streaming(name='with fire', url='https://twitch.tv/R_R4R'))
        print(f'Successfully logged in and booted...!')
        channel = self.bot.get_channel(676288007556300830)
        self.channel = channel
        await channel.connect()
        self.ctx = 0
        await self.next()
        self.dlnum2 = 0
        
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if self.dlnum2 == 1:
            await asyncio.sleep(5)
        play = False
        for member in self.channel.members:
            if not member.voice.deaf and not member.bot and not member.voice.self_deaf:
                play = True
        print("hi")
        if play and self.paused:
            self.guildid.voice_client.resume()
            print("resumed")
            self.paused = False
        elif not play and not self.paused:
            self.guildid.voice_client.pause()
            print("paused")
            self.paused = True
            
    @commands.command(name='pause', aliases=['stop'])
    async def pause(self, ctx):
        if not self.paused:
            self.guildid.voice_client.pause()
            self.paused = True
        
    @commands.command(name='resume', aliases=['continue'])
    async def resume(self, ctx):
        if self.paused:
            self.guildid.voice_client.resume()
            self.paused = False

    @commands.command(name='join', aliases=['summon'])
    async def join(self, ctx):
        self.playing = False
        await ctx.voice_client.disconnect()
        self.channel = ctx.author.voice.channel
        await self.channel.connect()
        self.ctx = ctx
        await self.next()
    
    
    async def yt2(self, ctx, *args):      #Literally just because I cant call yt from within playlist add and both of em have the same code and I dont want to repeat it
        url = " ".join(args)
        self.ctx = ctx
        members = ctx.voice_client.channel.members
        memberids = []
        self.dlnum+=1
        self.dlqueue.append(self.dlnum)
        await self.dlq(self.dlnum)
        for member in members:
            memberids.append(member.id)
        if ctx.message.author.id in memberids and not ctx.message.author.voice.deaf and not ctx.message.author.voice.self_deaf:
            if not self.playing:
                worked = False
                x = 0
                try:
                    url, player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                    await self.mq.enqueue(ctx, player, url)
                    #ctx.voice_client.play(player, after=self.my_after)
                    self.ctx = ctx
                    self.playing = True
                    ctx.voice_client.stop()
                    self.dlqueue.pop(1)
                except:
                    print(error)
                    print("yt 1")
                    msg = await ctx.send(f'Could not add song, please try again')
                    self.dlqueue.pop(1)
                    await self.next()
                    await asyncio.sleep(10)
                    await msg.delete()
                
            else:
                print("2")
                try:
                    url, player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                    await self.mq.enqueue(ctx, player, url)
                    msg = await ctx.send(f'Added {player.title} to queue')
                    self.dlqueue.pop(1)
                    await asyncio.sleep(10)
                    await msg.delete()
                except Exception as error:
                    print(error)
                    print("yt 2")
                    msg = await ctx.send(f'Could not add song, please try again')
                    self.dlqueue.pop(1)
                    await self.next()
                    await asyncio.sleep(10)
                    await msg.delete()
                
        else:
            msg = await ctx.send('You are not in vc')
            self.dlqueue.pop(1)
            await asyncio.sleep(10)
            await msg.delete()
            
    @commands.command(name='yt', aliases=['play'])
    async def yt(self, ctx, *args):
        await self.yt2(ctx, *args)
        
            
    async def next(self):
        if not self.hyit:
            await self.mq.dequeue()
        temp = self.mq.isEmpty()
        if self.hyit:
            self.dlnum+=1
            self.dlqueue.append(self.dlnum)
            await self.dlq(self.dlnum)
            url, player = await YTDLSource.from_url("https://www.youtube.com/watch?v=WdnzvYvUucg", loop=self.bot.loop, stream=True)
            guildid = self.bot.get_guild(218751753179365376)
            guildid.voice_client.play(player, after=self.my_after)
            await self.mq.zeroqueue(self.ctx, player, "https://www.youtube.com/watch?v=WdnzvYvUucg")
            self.guildid = guildid
            self.dlqueue.pop(1)
            self.starttime = time.time()
            if self.ctx != 0:
                msg = await self.ctx.send('Now playing: {}'.format(player.title))
                await asyncio.sleep(10)
                await msg.delete()
        elif self.playing and not temp:
            self.dlnum+=1
            self.dlqueue.append(self.dlnum)
            await self.dlq(self.dlnum)
            print("3")
            try:
                player = self.mq.currentplayer()
                self.ctx = self.mq.currentctx()
                self.ctx.voice_client.play(player, after=self.my_after)
                msg = await self.ctx.send(f'Now playing: {player.title}')
                self.playing = True
                self.starttime = time.time()
                self.dlqueue.pop(1)
                await asyncio.sleep(10)
                await msg.delete()
            except Exception as error:
                print(error)
                print("next 1")
                msg = await self.ctx.send(f'Something went wrong, skipping song')
                self.dlqueue.pop(1)
                await self.next()
                await asyncio.sleep(10)
                await msg.delete()
        else:
            print("4")
            s=open(self.playlist,"r",encoding='utf8')
            m=s.readlines()
            url = ""
            end = random.randint(1, len(m))
            end += end%2 - 1
            print("this is", (end+1)/2)
            for i in range(0, end):
                x=m[i]
                z=len(x)
                url=x[:z-1]
            s.close()
            self.dlnum+=1
            self.dlqueue.append(self.dlnum)
            await self.dlq(self.dlnum)
            player = 0
            try:
                url, player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                await self.mq.enqueue(0, player, url)
                self.dlqueue.pop(1)
                guildid = self.bot.get_guild(218751753179365376)
                guildid.voice_client.play(player, after=self.my_after)
                self.guildid = guildid
                self.starttime = time.time()
                self.playing = False
            except Exception as error:
                print(error)
                print("next 2")
                self.dlqueue.pop(1)
                await self.next()
    
    def my_after(self, error):
        asyncio.run_coroutine_threadsafe(asyncio.sleep(1), self.bot.loop)
        try:
            fut = asyncio.run_coroutine_threadsafe(self.next(), self.bot.loop)
            fut.result()
        except Exception as e:
            print(e)
    
    
    
    
    
    
        
    async def skipinterface(self, ctx):
        self.ctx = ctx
        members = ctx.voice_client.channel.members
        embed = discord.Embed(description=f'Thumbs up to skip. {(int((len(members)-1)/2)+1)} needed', color=0x51719f)
        msg = await ctx.send(embed = embed)
        users = []
        def check(reaction, user):
            members = self.ctx.voice_client.channel.members
            memberids = []
            for member in members:
                memberids.append(member.id)
            totalreacts = 0
            if user.id not in users:
                users.append(user.id)
            print('ay')
            for usertemp in users:
                if (str(reaction.emoji) == '\U0001F44D') and usertemp in memberids:
                    totalreacts+=1
            print(totalreacts-1, " total reacts")
            print(int((len(memberids)-1)/2), " members")
            return totalreacts-1 > (len(memberids)-1)/2
        try:
            await msg.add_reaction('\U0001F44D' )
            reaction, user = await self.bot.wait_for('reaction_add', timeout =60.0, check = check)
        except asyncio.TimeoutError:
            await msg.edit(embed = discord.Embed(description="Skip message timed out", color=0x51719f))
            await asyncio.sleep(5)
            await msg.delete()
        else:
            await msg.edit(embed = discord.Embed(description="Song Skipped", color=0x51719f))
            ctx.voice_client.stop()
            await asyncio.sleep(5)
            await msg.delete()
                    
    @commands.command()
    async def skip(self, ctx):
        self.ctx = ctx
        members = ctx.voice_client.channel.members
        memberids = []
        for member in members:
            memberids.append(member.id)
        if ctx.message.author.id ==218852384976273418:
            ctx.voice_client.stop()
        else:
            if ctx.message.author.id in memberids and not ctx.message.author.voice.deaf and not ctx.message.author.voice.self_deaf:
                if len(memberids) > 3:
                    await self.skipinterface(ctx)
                else:
                    ctx.voice_client.stop()
            else:
                await ctx.send('You are not in vc')
        
    async def qinterface(self, ctx, length):
        self.ctx = ctx
        embed=discord.Embed(description='Right or Left to move through the list', color=0x51719f)
        msg = await ctx.send(embed=embed)
        basej=1
        def check(reaction, user):
            nonlocal basej
            if user == ctx.message.author:
                if str(reaction.emoji) == '\U00002B05' and basej != 1:
                    basej -= 10
                elif str(reaction.emoji) == '\U000027A1' and basej < length-10:
                    basej += 10
                y = self.mq.getplayer(0)
                titlestr = (f'Playing: {y.title}\n')
                finalstr = ""
                max = 10
                print(length, basej)
                if length - basej < 10:
                    max = length - basej 
                for x in range(max):
                    y = self.mq.getplayer(x+basej)
                    finalstr+=(f'[**{(x+basej)}**]({self.mq.geturl(x+basej)}): {y.title}\n')
                embed=discord.Embed(title=titlestr,url = self.mq.geturl(0),description=finalstr, color=0x51719f)
                asyncio.run_coroutine_threadsafe(msg.edit(embed=embed), self.bot.loop)
                
            return False
        
        try:
            y = self.mq.getplayer(0)
            titlestr = (f'Playing: {y.title}\n')
            finalstr = ""
            max = 10
            if length - basej < 10:
                max = length - basej 
            for x in range(max):
                y = self.mq.getplayer(x+basej)
                finalstr+=(f'[**{(x+basej)}**]({self.mq.geturl(x+basej)}): {y.title}]\n')
            embed=discord.Embed(title=titlestr,url = self.mq.geturl(0),description=finalstr, color=0x51719f)
            await msg.edit(embed=embed)
            await msg.add_reaction('\U00002B05' )
            await msg.add_reaction('\U000027A1' )
            reaction, user = await self.bot.wait_for('reaction_add', timeout =120.0, check = check)
        except asyncio.TimeoutError:
            await msg.delete()
            
    @commands.command()      
    async def np(self, ctx):
        y = self.mq.getplayer(0)
        titlestr = (f'Playing: {y.title}\n')
        elapsed = time.time() - self.starttime
        descriptionstr = ''
        if self.mq.currentctx() != 0:
            descriptionstr = (f'Queued by {self.mq.currentctx().message.author.nick} \n')
        descriptionstr += (f'{elapsed} / {self.mq.currentplayer().duration}')
        length = self.mq.size()
        embed=discord.Embed(title=titlestr, description=descriptionstr, url = self.mq.geturl(0),color=0x51719f)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(30)
        await msg.delete()
        
    @commands.command()
    async def queue(self, ctx):
        y = self.mq.getplayer(0)
        finalstr = ""
        titlestr = (f'Playing: {y.title}\n')
        length = self.mq.size()
        if not self.hyit and length > 11:
            await self.qinterface(ctx, length)
        elif not self.hyit and length > 1:
            for x in range(length-1):
                y = self.mq.getplayer(x+1)
                finalstr+=(f'[**{(x+1)}**]({self.mq.geturl(x+1)}): {y.title}\n')
                embed=discord.Embed(title=titlestr,url = self.mq.geturl(0),description=finalstr, color=0x51719f)
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(60)
            await msg.delete()
        else:
            embed=discord.Embed(title=titlestr, url = self.mq.geturl(0),color=0x51719f)
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(30)
            await msg.delete()
    
    @commands.command()
    async def search(self, ctx, *args):
        url = " ".join(args)
        await ctx.send(ans)
    
    @commands.command(name='leave')
    async def leave(self, ctx):
        self.playing = False
        await ctx.voice_client.disconnect()
    
    
    @commands.command(name='hyoriittai', aliases=['hyit', 'hyori'])
    async def hyoriittai(self, ctx):
        if ctx.message.author.id == 218852384976273418:
            self.hyit = not self.hyit
            self.ctx = ctx
            ctx.voice_client.stop()
    
    @commands.group()
    async def playlist(self, ctx):
        if ctx.invoked_subcommand is None:
            msg = await ctx.send("Invalid command")
            await asyncio.sleep(10)
            await msg.delete()
    
    @playlist.command()
    async def add(self, ctx, *args):
        url = " ".join(args)
        person = "playlists/"+str(ctx.message.author.id)+".txt"
        try:
            f = open(person, "a+", encoding='utf8')
            self.dlnum+=1
            self.dlqueue.append(self.dlnum)
            await self.dlq(self.dlnum)
            url, temp = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            self.dlqueue.pop(1)
            f.write(url + "\n" + temp.title + "\n")
            f.close()
            embed=discord.Embed(description="Your song has been added to the playlist.", color=0x51719f)
            await ctx.send(embed=embed)
        except Exception as error:
            print(error)
            embed=discord.Embed(description="Invalid url", color=0x51719f)
            await ctx.send(embed=embed)
    
    @playlist.command()
    async def addlist(self, ctx, url):
        if 'playlist?list=' in url:
            person = "playlists/"+str(ctx.message.author.id)+".txt"
            await YTDLSource.addplaylist(url, person, self.bot.loop, ctx)
        else:
            msg = await ctx.send("Not a YouTube playlist")
            await asyncio.sleep(10)
            await msg.delete()
    
    @playlist.command(name='addnp', aliases=['addcurrent'])
    async def addnp(self, ctx):
        person = "playlists/"+str(ctx.message.author.id)+".txt"
        f = open(person, "a+", encoding='utf8')
        url = self.mq.currenturl()
        self.dlnum+=1
        self.dlqueue.append(self.dlnum)
        await self.dlq(self.dlnum)
        url, temp = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
        self.dlqueue.pop(1)
        f.write(url + "\n" + temp.title + "\n")
        f.close()
        embed=discord.Embed(description="The current song has been added to the playlist.", color=0x51719f)
        await ctx.send(embed=embed)
    
    
    async def listinterface(self, ctx, person):
        self.ctx = ctx
        embed=discord.Embed(description='Right or Left to move through the list', color=0x51719f)
        msg = await ctx.send(embed=embed)
        max = 1
        f2 = open(person, "r", encoding='utf8')
        for line in f2:
            line = f2.readline()
            max+=1
        basex = 1
        def check(reaction, user):
            nonlocal basex, max
            if user == ctx.message.author:
                if str(reaction.emoji) == '\U00002B05' and basex != 1:
                    basex -= 10
                elif str(reaction.emoji) == '\U000027A1' and basex < max-10:
                    basex += 10
                
                f = open(person, "r", encoding='utf8')
                finalstr = ""
                x = 1
                for line in f:
                    line = f.readline()
                    if x >= basex:
                        finalstr += str(x)+": " + line + "\n"
                    x+=1
                    if x == basex+10:
                        break
                f.close()
                embed=discord.Embed(description=finalstr, color=0x51719f)
                asyncio.run_coroutine_threadsafe(msg.edit(embed=embed), self.bot.loop)
                
            return False
        
        try:
            f = open(person, "r", encoding='utf8')
            finalstr = ""
            if f.readline() == "":
                raise Exception("no list")
            f.seek(0)
            x = 1
            for line in f:
                line = f.readline()
                if x >= 1:
                    finalstr += str(x)+": " + line + "\n"
                x+=1
                if x == 11:
                    break
            f.close()
            embed=discord.Embed(description=finalstr, color=0x51719f)
            await msg.edit(embed=embed)
            await msg.add_reaction('\U00002B05' )
            await msg.add_reaction('\U000027A1' )
            reaction, user = await self.bot.wait_for('reaction_add', timeout =120.0, check = check)
        except asyncio.TimeoutError:
            await msg.edit(embed = discord.Embed(description="List message timed out", color=0x51719f))
            await asyncio.sleep(5)
            await msg.delete()
        except Exception as error:
            print(error)
            embed=discord.Embed(description="You do not have a playlist", color=0x51719f)
            await ctx.send(embed=embed)
            
    @playlist.command()
    async def list(self, ctx, user:discord.User = None):
        mentioned = False
        if user != None:
            try:
                name = user.display_name
                mentioned = True
            except Exception as error:
                print(error)
        person = ""
        if not mentioned:
            person = "playlists/"+str(ctx.message.author.id)+".txt"
        else:
            person = "playlists/"+str(user.id)+".txt"
        await self.listinterface(ctx, person)
        
    
    @playlist.command()
    async def clear(self, ctx):
        person = "playlists/"+str(ctx.message.author.id)+".txt"
        f = open(person, "r+", encoding='utf8')
        f.truncate(0)
        f.close()
        embed=discord.Embed(description="Playlist has been cleared", color=0x51719f)
        await ctx.send(embed=embed)
        
    @playlist.command()
    async def play(self, ctx, num:int):
        self.ctx = ctx
        members = ctx.voice_client.channel.members
        memberids = []
        for member in members:
            memberids.append(member.id)
        if ctx.message.author.id in memberids and not ctx.message.author.voice.deaf and not ctx.message.author.voice.self_deaf:
            person = "playlists/"+str(ctx.message.author.id)+".txt"
            try:
                f = open(person, "r", encoding='utf8')
                x = 1
                queued = False
                num = num*2 -1
                for line in f:
                    if x == 1 and line == "":
                        raise Exception("You do not have a playlist")
                    if x == num and line != "":
                        await self.yt2(ctx, line)
                        queued = True
                    x+=1
                if not queued:
                    embed=discord.Embed(description="No song was queued", color=0x51719f)
                    await ctx.send(embed=embed)
            except Exception as error:
                embed=discord.Embed(description=error, color=0x51719f)
                await ctx.send(embed=embed)
        else:
            embed=discord.Embed(description='You are not in vc', color=0x51719f)
            await ctx.send(embed=embed)
    
    async def setinterface(self, ctx, person):
        self.ctx = ctx
        members = ctx.voice_client.channel.members
        msg = await ctx.send(f'Thumbs up to set. {(int((len(members)-1)/2)+1)} needed')
        users = []
        def check(reaction, user):
            members = self.ctx.voice_client.channel.members
            memberids = []
            for member in members:
                memberids.append(member.id)
            totalreacts = 0
            if user.id not in users:
                users.append(user.id)
            print('ay')
            for usertemp in users:
                if (str(reaction.emoji) == '\U0001F44D') and usertemp in memberids:
                    totalreacts+=1
            print(totalreacts-1, " total reacts")
            print(int((len(memberids)-1)/2), " members")
            return totalreacts-1 > (len(memberids)-1)/2
        try:
            await msg.add_reaction('\U0001F44D' )
            reaction, user = await self.bot.wait_for('reaction_add', timeout =120.0, check = check)
        except asyncio.TimeoutError:
            await msg.delete()
        else:
            name = ctx.message.author.display_name
            embed=discord.Embed(description=f"Set playlist to {name}'s playlist", color=0x51719f)
            self.playlist = person
            
    @playlist.command()
    async def set(self, ctx, user:discord.User = None):
        self.ctx = ctx
        members = ctx.voice_client.channel.members
        memberids = []
        for member in members:
            memberids.append(member.id)
        if ctx.message.author.id in memberids:
            mentioned = False
            if user != None:
                try:
                    name = user.display_name
                    mentioned = True
                except Exception as error:
                    print(error)
            print(ctx.message.author.id +1)
            if not mentioned:
                try:
                    person = "playlists/"+str(ctx.message.author.id)+".txt"
                    f = open(person, "r", encoding='utf8')
                    f.close()
                    if len(memberids) > 2 and ctx.message.author.id != 218852384976273418:
                        await self.setinterface(ctx, person)
                    else:
                        self.playlist = person
                        name = ctx.message.author.display_name
                        embed=discord.Embed(description=f"Set playlist to {name}'s playlist", color=0x51719f)
                        await ctx.send(embed=embed)
                except:
                    embed=discord.Embed(description="You do not have a playlist", color=0x51719f)
                    await ctx.send(embed=embed)
            else:
                try:
                    name = user.display_name
                    person = "playlists/"+str(user.id)+".txt"
                    f = open(person, "r", encoding='utf8')
                    f.close()
                    if len(memberids) > 2 and ctx.message.author.id != 732782378170318968:
                        await self.setinterface(ctx, person)
                    else:
                        self.playlist = person
                    embed=discord.Embed(description=f"Set playlist to {name}'s playlist", color=0x51719f)
                    await ctx.send(embed=embed)
                except:
                    embed=discord.Embed(description="They do not have a playlist", color=0x51719f)
                    await ctx.send(embed=embed)
            
        else:
            await ctx.send('You are not in vc')
            
            
        
                
        
                
    
    @playlist.command()
    async def reset(self, ctx):
        self.playlist = "autoplaylist.txt"
        
    @playlist.command()
    async def remove(self, ctx, num:int, num2:int = 0):
        person = "playlists/"+str(ctx.message.author.id)+".txt"
        try:
            f = open(person, "r+", encoding='utf8')
            x = 1
            finalstr = ""
            if f.readline() == "":
                raise Exception("no list")
            f.seek(0)
            num*=2
            sendstr = ""
            for line in f:
                print(line)
                if x != num and x != num-1:
                    print(x, " ", num)
                    did = True
                    finalstr +=line
                if x == num:
                    sendstr = line
                x+=1
            f.seek(0)
            f.truncate(0)
            f.write(finalstr)
            f.close()
            if sendstr != "":
                embed=discord.Embed(description=f"Removed {sendstr} from playlist", color=0x51719f)
                await ctx.send(embed=embed)
            else:
                embed=discord.Embed(description="Nothing was changed", color=0x51719f)
                await ctx.send(embed=embed)
        except Exception as error:
            print(error)
            embed=discord.Embed(description="You do not have a playlist", color=0x51719f)
            await ctx.send(embed=embed)
            
def setup(bot):
    bot.add_cog(MusicCog(bot))

