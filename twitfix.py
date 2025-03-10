from flask import Flask, render_template, request, redirect, Response, send_from_directory, url_for, send_file, make_response
import youtube_dl
import textwrap
import twitter
import pymongo
import requests
import json
import re
import os
import urllib.parse
import urllib.request

app = Flask(__name__)
pathregex = re.compile("\\w{1,15}\\/(status|statuses)\\/\\d{2,20}")
generate_embed_user_agents = [
    "facebookexternalhit/1.1", 
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/601.2.4 (KHTML, like Gecko) Version/9.0.1 Safari/601.2.4 facebookexternalhit/1.1 Facebot Twitterbot/1.0", 
    "facebookexternalhit/1.1", 
    "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)", 
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:38.0) Gecko/20100101 Firefox/38.0", 
    "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)", 
    "TelegramBot (like TwitterBot)", 
    "Mozilla/5.0 (compatible; January/1.0; +https://gitlab.insrt.uk/revolt/january)", 
    "test"]

# Read config from config.json. If it does not exist, create new.
if not os.path.exists("config.json"):
    with open("config.json", "w") as outfile:
        default_config = {
            "config":{
                "link_cache":"json",
                "database":"[url to mongo database goes here]",
                "method":"youtube-dl", 
                "color":"#43B581", 
                "appname": "TwitFix", 
                "repo": "https://github.com/robinuniverse/twitfix", 
                "url": "https://fxtwitter.com"
                },
            "api":{"api_key":"[api_key goes here]",
            "api_secret":"[api_secret goes here]",
            "access_token":"[access_token goes here]",
            "access_secret":"[access_secret goes here]"
            }
        }

        json.dump(default_config, outfile, indent=4, sort_keys=True)

    config = default_config
else:
    f = open("config.json")
    config = json.load(f)
    f.close()

# If method is set to API or Hybrid, attempt to auth with the Twitter API
if config['config']['method'] in ('api', 'hybrid'):
    auth = twitter.oauth.OAuth(config['api']['access_token'], config['api']['access_secret'], config['api']['api_key'], config['api']['api_secret'])
    twitter_api = twitter.Twitter(auth=auth)

link_cache_system = config['config']['link_cache']

if link_cache_system == "json":
    link_cache = {}
    if not os.path.exists("config.json"):
        with open("config.json", "w") as outfile:
            default_link_cache = {"test":"test"}
            json.dump(default_link_cache, outfile, indent=4, sort_keys=True)

    f = open('links.json',)
    link_cache = json.load(f)
    f.close()
elif link_cache_system == "db":
    client = pymongo.MongoClient(config['config']['database'], connect=False)
    db = client.TwitFix

@app.route('/bidoof/')
def bidoof():
    return redirect("https://cdn.discordapp.com/attachments/291764448757284885/937343686927319111/IMG_20211226_202956_163.webp", 301)

@app.route('/latest/') # Try to return the latest video
def latest():
	vnf     = db.linkCache.find_one(sort = [('_id', pymongo.DESCENDING)])
	desc    = re.sub(r' http.*t\.co\S+', '', vnf['description'])
	urlUser = urllib.parse.quote(vnf['uploader'])
	urlDesc = urllib.parse.quote(desc)
	urlLink = urllib.parse.quote(vnf['url'])
	print(" ➤ [ ✔ ] Latest video page loaded: " + vnf['tweet'] )
	return render_template('inline.html', page="Latest", vidlink=vnf['url'], vidurl=vnf['url'], desc=desc, pic=vnf['thumbnail'], user=vnf['uploader'], video_link=vnf['url'], color=config['config']['color'], appname=config['config']['appname'], repo=config['config']['repo'], url=config['config']['url'], urlDesc=urlDesc, urlUser=urlUser, urlLink=urlLink, tweet=vnf['tweet'])

@app.route('/top/') # Try to return the most hit video
def top():
	vnf     = db.linkCache.find_one(sort = [('hits', pymongo.DESCENDING)])
	desc    = re.sub(r' http.*t\.co\S+', '', vnf['description'])
	urlUser = urllib.parse.quote(vnf['uploader'])
	urlDesc = urllib.parse.quote(desc)
	urlLink = urllib.parse.quote(vnf['url'])
	print(" ➤ [ ✔ ] Top video page loaded: " + vnf['tweet'] )
	return render_template('inline.html', page="Top", vidlink=vnf['url'], vidurl=vnf['url'], desc=desc, pic=vnf['thumbnail'], user=vnf['uploader'], video_link=vnf['url'], color=config['config']['color'], appname=config['config']['appname'], repo=config['config']['repo'], url=config['config']['url'], urlDesc=urlDesc, urlUser=urlUser, urlLink=urlLink, tweet=vnf['tweet'])

@app.route('/') # If the useragent is discord, return the embed, if not, redirect to configured repo directly
def default():
    user_agent = request.headers.get('user-agent')
    if user_agent in generate_embed_user_agents:
        return message("TwitFix is an attempt to fix twitter video embeds in discord! created by Robin Universe :)\n\n💖\n\nClick me to be redirected to the repo!")
    else:
        return redirect(config['config']['repo'], 301)

@app.route('/oembed.json') #oEmbed endpoint
def oembedend():
    desc  = request.args.get("desc", None)
    user  = request.args.get("user", None)
    link  = request.args.get("link", None)
    ttype = request.args.get("ttype", None)
    return  oEmbedGen(desc, user, link, ttype)

@app.route('/<path:sub_path>') # Default endpoint used by everything
def twitfix(sub_path):
    user_agent = request.headers.get('user-agent')
    match = pathregex.search(sub_path)

    if request.url.startswith("https://d.fx"): # Matches d.fx? Try to give the user a direct link
        if user_agent in generate_embed_user_agents:
            print( " ➤ [ D ] d.fx link shown to discord user-agent!")
            if request.url.endswith(".mp4") and "?" not in request.url:
                return dl(sub_path)
            else:
                return message("To use a direct MP4 link in discord, remove anything past '?' and put '.mp4' at the end")
        else:
            print(" ➤ [ R ] Redirect to MP4 using d.fxtwitter.com")
            return dir(sub_path)

    elif sub_path.endswith(".mp4"):
        if "?" not in request.url:
            return dl(sub_path)
        else:
            return message("To use a direct MP4 link in discord, remove anything past '?' and put '.mp4' at the end")
        
    if match is not None:
        twitter_url = sub_path

        if match.start() == 0:
            twitter_url = "https://twitter.com/" + sub_path

        if user_agent in generate_embed_user_agents:
            res = embed_video(twitter_url)
            return res

        else:
            print(" ➤ [ R ] Redirect to " + twitter_url)
            return redirect(twitter_url, 301)
    else:
        return message("This doesn't appear to be a twitter URL")

@app.route('/other/<path:sub_path>') # Show all info that Youtube-DL can get about a video as a json
def other(sub_path):
    otherurl = request.url.split("/other/", 1)[1].replace(":/","://")
    print(" ➤ [ OTHER ]  Other URL embed attempted: " + otherurl)
    res = embed_video(otherurl)
    return res

@app.route('/info/<path:sub_path>') # Show all info that Youtube-DL can get about a video as a json
def info(sub_path):
    infourl = request.url.split("/info/", 1)[1].replace(":/","://")
    print(" ➤ [ INFO ] Info data requested: " + infourl)
    with youtube_dl.YoutubeDL({'outtmpl': '%(id)s.%(ext)s'}) as ydl:
        result = ydl.extract_info(infourl, download=False)

    return result

@app.route('/dl/<path:sub_path>') # Download the tweets video, and rehost it
def dl(sub_path):
    print(' ➤ [[ !!! TRYING TO DOWNLOAD FILE !!! ]] Downloading file from ' + sub_path)
    url   = sub_path
    match = pathregex.search(url)
    if match is not None:
        twitter_url = url
        if match.start() == 0:
            twitter_url = "https://twitter.com/" + url
    
    mp4link  = direct_video_link(twitter_url)
    filename = (sub_path.split('/')[-1].split('.mp4')[0] + '.mp4')

    PATH = ( './static/' + filename )
    if os.path.isfile(PATH) and os.access(PATH, os.R_OK):
        print(" ➤ [[ FILE EXISTS ]]")
    else:
        print(" ➤ [[ FILE DOES NOT EXIST, DOWNLOADING... ]]")
        mp4file = urllib.request.urlopen(mp4link)
        with open(('/home/robin/twitfix/static/' + filename), 'wb') as output:
            output.write(mp4file.read())

    print(' ➤ [[ PRESENTING FILE: '+ filename +', URL: https://fxtwitter.com/static/'+ filename +' ]]')
    r = make_response(send_file(('static/' + filename), mimetype='video/mp4', max_age=100))
    r.headers['Content-Type']   = 'video/mp4'
    r.headers['Sec-Fetch-Site'] = 'none'
    r.headers['Sec-Fetch-User'] = '?1'
    return r
	
@app.route('/dir/<path:sub_path>') # Try to return a direct link to the MP4 on twitters servers
def dir(sub_path):
    user_agent = request.headers.get('user-agent')
    url   = sub_path
    match = pathregex.search(url)
    if match is not None:
        twitter_url = url

        if match.start() == 0:
            twitter_url = "https://twitter.com/" + url

        if user_agent in generate_embed_user_agents:
            res = embed_video(twitter_url)
            return res

        else:
            print(" ➤ [ R ] Redirect to direct MP4 URL")
            return direct_video(twitter_url)
    else:
        return redirect(url, 301)

@app.route('/favicon.ico') # This shit don't work
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                          'favicon.ico',mimetype='image/vnd.microsoft.icon')

def direct_video(video_link): # Just get a redirect to a MP4 link from any tweet link
    cached_vnf = getVnfFromLinkCache(video_link)
    if cached_vnf == None:
        try:
            vnf = link_to_vnf(video_link)
            addVnfToLinkCache(video_link, vnf)
            return redirect(vnf['url'], 301)
            print(" ➤ [ D ] Redirecting to direct URL: " + vnf['url'])
        except Exception as e:
            print(e)
            return message("Failed to scan your link!")
    else:
        return redirect(cached_vnf['url'], 301)
        print(" ➤ [ D ] Redirecting to direct URL: " + vnf['url'])

def direct_video_link(video_link): # Just get a redirect to a MP4 link from any tweet link
    cached_vnf = getVnfFromLinkCache(video_link)
    if cached_vnf == None:
        try:
            vnf = link_to_vnf(video_link)
            addVnfToLinkCache(video_link, vnf)
            return vnf['url']
            print(" ➤ [ D ] Redirecting to direct URL: " + vnf['url'])
        except Exception as e:
            print(e)
            return message("Failed to scan your link!")
    else:
        return cached_vnf['url']
        print(" ➤ [ D ] Redirecting to direct URL: " + vnf['url'])

def embed_video(video_link): # Return Embed from any tweet link
    cached_vnf = getVnfFromLinkCache(video_link)

    if cached_vnf == None:
        try:
            vnf = link_to_vnf(video_link)
            addVnfToLinkCache(video_link, vnf)
            return embed(video_link, vnf)

        except Exception as e:
            print(e)
            return message("Failed to scan your link!")
    else:
        return embed(video_link, cached_vnf)

def tweetInfo(url, tweet="", desc="", thumb="", uploader="", screen_name="", pfp="", tweetType="", image="", hits=0, likes=0, rts=0, time="", qrt={}): # Return a dict of video info with default values
    vnf = {
        "tweet"         : tweet,
        "url"           : url,
        "description"   : desc,
        "thumbnail"     : thumb,
        "uploader"      : uploader,
        "screen_name"   : screen_name,
        "pfp"           : pfp,
        "type"          : tweetType,
        "image"         : image,
        "hits"          : hits,
        "likes"         : likes,
        "rts"           : rts,
        "time"          : time,
        "qrt"           : qrt
    }
    return vnf

def link_to_vnf_from_api(video_link):
    print(" ➤ [ + ] Attempting to download tweet info from Twitter API")
    twid = int(re.sub(r'\?.*$','',video_link.rsplit("/", 1)[-1])) # gets the tweet ID as a int from the passed url
    tweet = twitter_api.statuses.show(_id=twid, tweet_mode="extended")
    #print(tweet)
    print(" ➤ [ + ] Tweet Type: " + tweetType(tweet))
    # Check to see if tweet has a video, if not, make the url passed to the VNF the first t.co link in the tweet
    if tweetType(tweet) == "Video":
        if tweet['extended_entities']['media'][0]['video_info']['variants'][-1]['content_type'] == "video/mp4":
            url   = tweet['extended_entities']['media'][0]['video_info']['variants'][-1]['url']
            thumb = tweet['extended_entities']['media'][0]['media_url']
        else:
            url   = tweet['extended_entities']['media'][0]['video_info']['variants'][-2]['url']
            thumb = tweet['extended_entities']['media'][0]['media_url']
    elif tweetType(tweet) == "Text":
        url   = ""
        thumb = ""
    else:
        url   = ""
        thumb = tweet['extended_entities']['media'][0]['media_url']

    qrt = {}

    if 'quoted_status' in tweet:
        qrt['desc']       = tweet['quoted_status']['full_text']
        qrt['handle']     = tweet['quoted_status']['user']['name']
        qrt['screenname'] = tweet['quoted_status']['user']['screen_name']

    text = tweet['full_text']

    vnf = tweetInfo(url, video_link, text, thumb, tweet['user']['name'], tweet['user']['screen_name'], tweet['user']['profile_image_url'], tweetType(tweet), likes=tweet['favorite_count'], rts=tweet['retweet_count'], time=tweet['created_at'], qrt=qrt)
    return vnf

def link_to_vnf_from_youtubedl(video_link):
    print(" ➤ [ X ] Attempting to download tweet info via YoutubeDL: " + video_link)
    with youtube_dl.YoutubeDL({'outtmpl': '%(id)s.%(ext)s'}) as ydl:
        result = ydl.extract_info(video_link, download=False)
        vnf    = tweetInfo(result['url'], video_link, result['description'].rsplit(' ',1)[0], result['thumbnail'], result['uploader'])
        return vnf

def link_to_vnf(video_link): # Return a VideoInfo object or die trying
    if config['config']['method'] == 'hybrid':
        try:
            return link_to_vnf_from_api(video_link)
        except Exception as e:
            print(" ➤ [ !!! ] API Failed")
            print(e)
            return link_to_vnf_from_youtubedl(video_link)
    elif config['config']['method'] == 'api':
        try:
            return link_to_vnf_from_api(video_link)
        except Exception as e:
            print(" ➤ [ X ] API Failed")
            print(e)
            return None
    elif config['config']['method'] == 'youtube-dl':
        try:
            return link_to_vnf_from_youtubedl(video_link)
        except Exception as e:
            print(" ➤ [ X ] Youtube-DL Failed")
            print(e)
            return None
    else:
        print("Please set the method key in your config file to 'api' 'youtube-dl' or 'hybrid'")
        return None

def getVnfFromLinkCache(video_link):
    if link_cache_system == "db":
        collection = db.linkCache
        vnf        = collection.find_one({'tweet': video_link})
        # print(vnf)
        if vnf != None: 
            hits   = ( vnf['hits'] + 1 ) 
            print(" ➤ [ ✔ ] Link located in DB cache. " + "hits on this link so far: [" + str(hits) + "]")
            query  = { 'tweet': video_link }
            change = { "$set" : { "hits" : hits } }
            out    = db.linkCache.update_one(query, change)
            return vnf
        else:
            print(" ➤ [ X ] Link not in DB cache")
            return None
    elif link_cache_system == "json":
        if video_link in link_cache:
            print("Link located in json cache")
            vnf = link_cache[video_link]
            return vnf
        else:
            print(" ➤ [ X ] Link not in json cache")
            return None

def addVnfToLinkCache(video_link, vnf):
    if link_cache_system == "db":
        try:
            out = db.linkCache.insert_one(vnf)
            print(" ➤ [ + ] Link added to DB cache ")
            return True
        except Exception:
            print(" ➤ [ X ] Failed to add link to DB cache")
            return None
    elif link_cache_system == "json":
        link_cache[video_link] = vnf
        with open("links.json", "w") as outfile: 
            json.dump(link_cache, outfile, indent=4, sort_keys=True)
            return None

def message(text):
    return render_template(
        'default.html', 
        message = text, 
        color   = config['config']['color'], 
        appname = config['config']['appname'], 
        repo    = config['config']['repo'], 
        url     = config['config']['url'] )

def embed(video_link, vnf):
    print(" ➤ [ E ] Embedding " + vnf['type'] + ": " + vnf['url'])
    
    desc    = re.sub(r' http.*t\.co\S+', '', vnf['description'])
    urlUser = urllib.parse.quote(vnf['uploader'])
    urlDesc = urllib.parse.quote(desc)
    urlLink = urllib.parse.quote(video_link)
    likeDisplay = ("\n─────────────\n ♥ [" + str(vnf['likes']) + "] ⤴ [" + str(vnf['rts']) + "]\n─────────────")
    
    try:
        if vnf['type'] == "Video":
            desc = desc
        elif vnf['qrt'] == {}: # Check if this is a QRT and modify the description
            desc = (desc + likeDisplay)
        else:
            qrtDisplay = ("\n─────────────\n ➤ QRT of " + vnf['qrt']['handle'] + " (@" + vnf['qrt']['screenname'] + "):\n─────────────\n'" + vnf['qrt']['desc'] + "'")
            desc = (desc + qrtDisplay +  likeDisplay)
    except:
        vnf['likes'] = 0; vnf['rts'] = 0; vnf['time'] = 0
        print(' ➤ [ X ] Failed QRT check - old VNF object')
        
    if vnf['type'] == "Text": # Change the template based on tweet type
        template = 'text.html'
    if vnf['type'] == "Image":
        template = 'image.html'
    if vnf['type'] == "Video":
        urlDesc = urllib.parse.quote(textwrap.shorten(desc, width=220, placeholder="..."))
        template = 'video.html'

    return render_template(
        template, 
        likes      = vnf['likes'], 
        rts        = vnf['rts'], 
        time       = vnf['time'], 
        screenName = vnf['screen_name'], 
        vidlink    = vnf['url'], 
        pfp        = vnf['pfp'],  
        vidurl     = vnf['url'], 
        desc       = desc,
        pic        = vnf['thumbnail'], 
        user       = vnf['uploader'], 
        video_link = video_link, 
        color      = config['config']['color'], 
        appname    = config['config']['appname'], 
        repo       = config['config']['repo'], 
        url        = config['config']['url'], 
        urlDesc    = urlDesc, 
        urlUser    = urlUser, 
        urlLink    = urlLink )

def tweetType(tweet): # Are we dealing with a Video, Image, or Text tweet?
    if 'extended_entities' in tweet:
        if 'video_info' in tweet['extended_entities']['media'][0]:
            out = "Video"
        else:
            out = "Image"
    else:
        out = "Text"

    return out


def oEmbedGen(description, user, video_link, ttype):
    out = {
            "type"          : ttype,
            "version"       : "1.0",
            "provider_name" : config['config']['appname'],
            "provider_url"  : config['config']['repo'],
            "title"         : description,
            "author_name"   : user,
            "author_url"    : video_link
            }

    return out

if __name__ == "__main__":
    app.config['SERVER_NAME']='localhost:80'
    app.run(host='0.0.0.0')
