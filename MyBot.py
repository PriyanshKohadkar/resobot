import os 
import discord
from discord.ext import commands
from discord import app_commands 
from dotenv import load_dotenv
import random

from keep_alive import keep_alive
keep_alive()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
  
client = discord.Client(intents=discord.Intents.all(), case_insenstive=True)
birthday_greets = ["hbd", "many many","happy birthday", "happy","cheers","returns"]
solve = ""
f_words_no = [ "fa", "fi", "fai","fla","fu","freak", "fell","func" "fuc", "fac", "facebook", "fs", "fd", "fg", "fh", "fj", "fl", "fm", "fn", "fb", "fv", "fc","fx", "fz", "fq", "ff", "fw", "fe", "fr", "ft", "fy", "fu", "fi", "fo", "fp", "fap","flap", "face", "fair","fuck","facts","fax","fk","fix", "fellow","fun", "function", "freaking", "wtf", "ofc", "of", "off", "if", "ig"]
pay_respects = ["f", "respects"]
birthday_greets_response = ["https://tenor.com/view/nico-yazawa-love-live-happy-birthday-gif-9241240", "https://tenor.com/view/happy-birthday-pokemon-dance-pikachu-gif-17058590", "https://tenor.com/view/naruto-shippuden-madara-uchiha-gif-5321987","https://tenor.com/view/fairy-tail-happy-birthday-twerk-virgo-booty-shake-gif-16086842", "https://tenor.com/view/naruto-naruto-chunin-exams-chunin-exams-dance-gif-13984229"]
murukh = ["idiot", "baka", "bakka", "noob", "lmao noob", "murukh"]
murukh_response = ["https://tenor.com/view/baka-anime-gif-12908346", "https://tenor.com/view/tobirama-baka-gif-18220803","https://tenor.com/view/sasuke-naruto-anime-mad-baka-gif-17737654"]
friends_words = ["besto friendo", "best friend", "true friend", "truu friend","you are my friend", "my besto friendo", "my best friend", "i am your friend",]
sad_words = ["sad", "depressed", "unhappy", "sed", "angry", "depressing", "miserable", "fucked up",]
starter_encouragements = [
"cheer up!",
"hang in there",
"you are a great person!",
"don't forget you are a sigma male!"
]
'''pydro_acc = "<@804358711136747551>"
malhar_acc = "<@926561667289063424>"
if "responding" not in db.keys():
  db["responding"] = True

def get_quote():
  response = requests.get("https://zenquotes.io/api/random")
  json_data = json.loads(response.text)
  quote = json_data[0]['q'] + " -" + json_data[0]['a']
  return(quote)
def update_encouragements(encouraging_message):
  if "encouragements" in db.keys():
    encouragements = db["encouragements"]  
    encouragements.append(encouraging_message)
    db["encouragements"] = encouragements
  else:
    db["encouragements"] = [encouraging_message]

def delete_encouragement(index):
  encouragements = db["encouragements"]
  if len(encouragements) > index:
    del encouragements[index]
'''

@client.event
async def on_ready():
  await client.change_presence(status=discord.Status.online, activity=discord.Game("$Ghelp"))
  print('we have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
  if message.author == client.user:
    return
  if message.mention_everyone:
    return
  else:
    if client.user.mentioned_in(message):
      await message.channel.send(f"I am here to help you!, {message.author.mention}")
  msg = message.content

  #if message.content.lower().startswith('hello'):
   # await message.channel.send('hello! I am here to help you!')#
  if message.content.lower().startswith('hindi'):
    return
  if message.content.lower().startswith('hi'):
    await message.channel.send('whatsup!')
  if message.content.lower().startswith("umai"):
    await message.channel.send('Umai!')

  if message.content.lower().startswith("thanks @Pythbot"):
    await message.channel.send("welcome happy to help you!")
  if message.content.lower().startswith("thank you <@923611772135546960>"):
    await message.channel.send("welcome happy to help you!")
  if message.content.lower().startswith("ok <@923611772135546960>"):
    await message.channel.send("done!")  
  if message.content.lower().startswith('$syllabus sst'):
    await message.channel.send("```GEOGRAPHY:- \n 1. Resources:Utilisation and Development \n 2.Natural resources:Land,Soil,Water \n 3.Natural resorces:Vegetation and Wildlife \n 4.Agriculture \n 5. Human Resources \n HISTORY:- \n 1.Modern Period \n 2.Establishment of Company Rule in India \n 3.Colonialism:Rural and Tribal socities \n 4. The First war of Independence -1857 \n 5.The nationalist movement(1870 to 1947)\n 6.India marches ahead \n CIVICS:- \n 1.Our Constitution \n 2.Fundamental rights ,Fundamental Duties and Directive Principles of State Policy \n 3.The Union Government: The legislature \n 4.The Union Government: The Executive \n 5.The Union Government:The Judiciary```")
  
  if message.content.lower().startswith('$send mark_scheme'):
    await message.channel.send("https://drive.google.com/file/d/1efqQQb9ZwuimTHyuszrEruiDpZJBNAT2/view?usp=sharing")

  if message.content.lower().startswith('$send sample_papers'):
    await message.channel.send("https://drive.google.com/file/d/1kWBrIjGjfNbCFshDK091vj0x2v-A4Z6W/view?usp=sharing") 

  if message.content.lower().startswith('$send'):
    await message.channel.send("```to get notes of any subjects type '$send <subject name>' (exclusives:- $send mark_scheme, $send sample_papers)```")
  if message.content.lower().startswith('$syllabus science'):
    await message.channel.send("syllabus has'nt been  uploaded yet")

  if message.content.lower().startswith('$syllabus'):
    await message.channel.send("to get syllabus of any subject type '$syllabus <subject name>'")

  if  message.content.lower().startswith('$examtable'):
    await message.channel.send('```the upcoming exam is going to be a preparetory! \n exam date: 17th january 2022! \n exam mode:- online(may change later depending upon current situation)``` \n ```(sr.no, date, day, subject format) \n 1. 17.01.2022 Monday English \n 2. 19.01.2022 Mathematics Wednesday \n 3. 21.01.2022 Friday Hindi \n 4. 24.01.2022 Monday Social Science \n 5. 27.01.2022 Thursday Science \n 6. 29.01.2022 Saturday Sanskrit / Marathi \n 7. 31.01.2022 Monday Moral Education``` \n ```1. The timing of examination shall be from 8.00 am to 11.00 am. \n 2. Students to be ready 10 minutes prior to the examination schedule. \n 3. Click clear image of answer sheets and convert images in a single pdf before uploading the subjective paper. \n 4. Please write your name, section and roll number on every page of answer sheet of your subjective paper. \n 5. Follow the instructions strictly and in case of any difficulty contact your class teacher. \n . In case if there is any change from the current situation we shall reschedule the mode, date and time of the examination and will be intimated.```\n  to get the image pls visit:- \n https://drive.google.com/file/d/1PN-DhPQsXiolIWWF5nwHToPV9BOX4JEf/view?usp=sharing \n download image from here ')

  if  message.content.lower().startswith('commands'):
    await message.channel.send("```some simple commands for the Pythobot:- \n $developer :- for developer information \n $responding true(for responding on) and $responding false(for responding off) \n $syllabus :- for the syllabus \n $examdate :- exam date \n $inspire :- for getting inspiration Quotes! \n $listencourage :- for getting current encouragement list \n $newencourage :- to add a newencouragement(ex. you are best! don't be sad) \n $delencourage :- for deleting encouragement messages (note:- the list start with 0, not with 1 index)```")

  if  message.content.lower().startswith('$ghelp'):
    await message.channel.send("```some simple commands for the Pythbot:- \n $developer :- for developer information \n $responding true(for responding on) and $responding false(for responding off) \n $syllabus :- for the syllabus \n $examdate :- exam date \n $inspire :- for getting inspiration Quotes! \n $listencourage :- for getting current encouragement list \n $newencourage :- to add a newencouragement(ex. you are best! don't be sad) \n $delencourage :- for deleting encouragement messages (note:- the list start with 0, not with 1 index) \n $send :- for getting notes of any subject or exam related```")

  if  message.content.lower().startswith('$developer'):
    await message.channel.send("This bot is developed and made by:- \n <@646008825224364042> \n github profile:- https://github.com/gunshotop \n replit.com:- https://replit.com/@Gunshotgaming \n Youtube channel:- https://www.youtube.com/channel/UC5Bf0ZVk7qi_CS1b15va6qw \n instagram profile:- https://www.instagram.com/gunshot.ig/ \n discord tag:- CODEGOD</>#5307 \n discord id:- '646008825224364042'")
  if message.content.lower().startswith('simple spell'):
    await message.channel.send('https://tenor.com/view/doctor-strange-marvel-simple-spell-unbreakable-gif-14530077')
  if message.content.lower().startswith('ohh yeah'):
    await message.channel.send('https://tenor.com/view/oh-yeah-gif-24167454')  
  if any(word in msg.lower() for word in friends_words):
    await message.channel.send('https://tenor.com/view/my-besto-friendo-jujutsu-kaisen-zorothex-gif-23553828')
  if any(word in msg.lower() for word in murukh):
      await message.channel.send(random.choice(murukh_response))  
  if message.content.lower().startswith('yes!'):
    await message.channel.send('https://tenor.com/view/jojo-anime-yes-yes-yes-yeah-its-a-yes-gif-17161748') 
  if message.content.lower().startswith('arigato'):
    await message.channel.send('https://c.tenor.com/5MAd4MUpoeEAAAAM/my-hero-academia-boku-no-hero-academia.gif')   
  if message.content.lower().startswith('chala ja'):
    await message.channel.send('https://tenor.com/view/chala-ja-chala-ja-b-sd-k-bsdk-chaleja-funnybawa-gif-18701954') 
  if message.content.lower().startswith('entertain'):
    await message.channel.send('https://tenor.com/view/eating-the-chip-chips-chip-eating-chip-man-eating-three-chips-gif-18885184')
  if message.content.lower().startswith('handshake'):
    await message.channel.send('https://tenor.com/view/madara-uchiha-hashirama-senju-hand-shake-gif-16768560')  
  if message.content.lower().startswith('hmm'):
    await message.channel.send("https://tenor.com/view/nani-intensifies-nani-intensifies-what-cosa-gif-13077558")
  if message.content.lower().startswith('i am god'):
    await message.channel.send("https://tenor.com/view/i-am-g-you-are-trash-i-am-superi-i-am-better-gif-24129609")  
  if message.content.lower().startswith('die'):
    await message.channel.send("https://tenor.com/view/naruto-from-behind-gif-13373335")
  if message.content.lower().startswith('shinee'):
    await message.channel.send("https://tenor.com/view/naruto-from-behind-gif-13373335") 
  if message.content.lower().startswith('jod'):
    await message.channel.send("https://tenor.com/view/tbone-jod-tbone-jod-raka-rakazone-gif-21986927")
  if any(word in msg.lower() for word in f_words_no):
    return
  elif any(word in msg.lower() for word in pay_respects):
    await message.channel.send ("https://tenor.com/view/pay-respects-press-f-call-of-duty-respect-press-x-gif-22309724")
        



#keep_alive()
client.run(TOKEN)   
