import json
import os
import PIL
import random
import requests
import telebot
import string
import tabulate
import urllib.parse
import numpy as np
from PIL import Image
from io import BytesIO
from datetime import datetime
from telebot.types import InlineQueryResultArticle, InputTextMessageContent

from johnson import johnson_image
from country_names import italian_names, english_names, italian_names_lower, english_names_lower, map_flags, map_guess

from keep_alive_ping import create_service

from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from schemas import *
service = create_service(ping_interval=600)

BOT_TOKEN = os.environ.get('BOT_TOKEN',"")
bot = telebot.TeleBot(BOT_TOKEN)


DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING","")
client=MongoClient(DB_CONNECTION_STRING)
db=client.get_database("main")

started = False
answer = ''
quiz_id = None
chat_quiz_id = None
flag_id = None
chat_flag_id = None
guessed_by = []
code = ""
flagling = False
flagled_done = []
last_flagled = None




def get_text(message):
    words = message.replace('\n', ' \n').split()
    return ' '.join(words[1:])

def escape_markdown_v2(text):
    chars_to_escape = ['-', '_', '(', ')', '+']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text

@bot.message_handler(commands=['start'])
def start(message):

    server_id=message.chat.id

    oracoin:Collection[Oracoin]=db["oracoin"]
    randoms:Collection[Random]=db["randoms"]
    polymarket:Collection[Polymarket]=db["polymarket"]
    

    if not oracoin.find_one({"server_id":server_id}):
        oracoin_base=Oracoin(
            server_id=server_id,
            data={}
        )
        oracoin.insert_one(oracoin_base)
    
    if not randoms.find_one({"server_id":server_id}):
        randoms_base=Random(
            server_id=server_id,
            randoms=[],
        )
        randoms.insert_one(randoms_base)

    if not polymarket.find_one({"server_id":server_id}):
        polymarket_base=Polymarket(
            server_id=server_id,
            polls={}
        )
        polymarket.insert_one(polymarket_base)
    
    bot.reply_to(message, '...')

@bot.message_handler(commands=['ciao'])
def ciao(message):
    print(message.chat.id)
    print(message.id)
    bot.reply_to(message, 'Buondì!')

@bot.message_handler(commands=['ora'])
def ora(message):
    bot.reply_to(message, 'A che ora è mate?')

@bot.message_handler(commands=['testo'])
def testo(message):
    name = get_text(message.text)
    url = 'https://training.olinfo.it/api/task'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'action': 'get',
        'name': ''
    }
    statement = {}

    prefix = ['', 'oii_', 'ois_', 'abc_', 'gator_', 'luiss_', 'mat_', 'preoii_', 'pre_boi_', 'pre-egoi-', 'roiti_', 'unimi_', 'weoi_']
    for i in prefix:
        data['name'] = i + name
        r = requests.post(url, headers=headers, data=json.dumps(data))
        statement = json.loads(r.text)
        print(data['name'])
        if statement['success'] == 1:
            name = data['name']
            break

    if statement['success'] == 1:
        ids = statement['statements']
        link = 'https://training.olinfo.it/api/files/' + (ids['it'] if 'it' in ids.keys() else ids['en']) + '/testo.pdf'
        tl = str(statement['time_limit']) + ' sec'
        ml = str(statement['memory_limit']/1048576) + ' MiB'
        pt = '<span class="tg-spoiler">' + str(round(statement['score_multiplier']*100)) + ' punti</span>'
        tg = ''
        for tag in statement['tags']:
            tg += '<span class="tg-spoiler">' + tag['name'] + '</span> '
        bot.send_document(message.chat.id, link, message.id, name + '\n' + pt + '\n' + tl + '\n' + ml + '\n' + tg, parse_mode='HTML')
    else:
        bot.reply_to(message, 'Nome del problema sbagliato. Riprovare.')

#-------------------------------------------------------------------------------------------------
#       _    ___    _   _   _   _   ____     ___    _   _     ____     ___    ___   _   _   _____ 
#      | |  / _ \  | | | | | \ | | / ___|   / _ \  | \ | |   |  _ \   / _ \  |_ _| | \ | | |_   _|
#   _  | | | | | | | |_| | |  \| | \___ \  | | | | |  \| |   | |_) | | | | |  | |  |  \| |   | |  
#  | |_| | | |_| | |  _  | | |\  |  ___) | | |_| | | |\  |   |  __/  | |_| |  | |  | |\  |   | |  
#   \___/   \___/  |_| |_| |_| \_| |____/   \___/  |_| \_|   |_|      \___/  |___| |_| \_|   |_|  
#--------------------------------------------------------------------------------------------------

def update_points(message,user_id, delta, username=None, correct=False, wrong=False):
    try:
        oracoin:Collection[Oracoin]=db["oracoin"]
        
        doc=oracoin.find_one({"server_id":message.chat.id})
        if doc is None:
            bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
            return
        
        
        row = doc["data"].get(str(user_id))
        if row:
            print(row["oracoins"])
            new_points = max(0, row["oracoins"] + delta)
            oracoin.find_one_and_update({"server_id":message.chat.id},{"$set":{f"data.{user_id}.oracoins":new_points}})
        else:
            initial_points = max(0, delta)
            base_data:OracoinUser={
                "oracoins":initial_points,
                "username":str(username),
                "locked_points":0,
            } 
            oracoin.find_one_and_update({"server_id":message.chat.id},{"$set":{f"data.{user_id}":base_data}})

    finally:
        pass


@bot.inline_handler(func=lambda query: query.query.startswith('johnson'))
def query_johnson(inline_query):
    query_text = inline_query.query[len('johnson'):].strip().lower().replace(' ', '_')

    results = []
    for solid in johnson_image:
        if query_text in solid:
            results.append(
                InlineQueryResultArticle(
                    id=solid,
                    title=solid.replace('_', ' ').capitalize(),
                    input_message_content=InputTextMessageContent(f'/johnson {solid}')
                )
            )
    results = results[:20]
    bot.answer_inline_query(inline_query.id, results)

@bot.message_handler(commands=['johnson'])
def johnson(message):
    global length
    text = get_text(message.text)
    textl = text.split()
    for i in range(len(textl)):
        textl[i] = textl[i].lower()
        if i == 0:
            text = textl[i]
        else:
            text += '_' + textl[i]  

    if text == '':
        solid = random.choice(johnson_image).capitalize()
        bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + solid + '.png', solid.replace('_', ' '), reply_to_message_id=message.id)
    elif text in johnson_image:
        solid = text.capitalize()
        bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + solid + '.png', solid.replace('_', ' '), reply_to_message_id=message.id)
    else:
        bot.reply_to(message, 'Solido non valido.')


@bot.message_handler(commands=['quiz'])
def quiz(message):
    global answer, quiz_id, chat_quiz_id, guessed_by
    options = random.sample(johnson_image, 3)
    answer = random.choice(options).replace('_', ' ')
    if quiz_id is not None and chat_quiz_id is not None:
        try:
            bot.delete_message(chat_quiz_id, quiz_id)
        except:
            pass

    markup = telebot.types.ReplyKeyboardMarkup()
    for item in options:
        markup.row(telebot.types.KeyboardButton('/ans ' + item.replace('_', ' ')))

    sent_msg = bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + answer.capitalize() + '.png', 'Che solido di Johnson è?', reply_to_message_id=message.id, reply_markup=markup)
    quiz_id = sent_msg.message_id
    chat_quiz_id = sent_msg.chat.id
    guessed_by = []

@bot.message_handler(commands=['ans'])
def ans(message):
    global answer, quiz_id, chat_quiz_id, guessed_by
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    markup = telebot.types.ReplyKeyboardRemove(selective=False)

    if answer == '':
        bot.reply_to(message, 'Nessun quiz in corso. Per avviarne uno usa /quiz.', reply_markup=markup)
    elif user_id not in guessed_by:
        guessed_by.append(user_id)
        if get_text(message.text) == answer:
            bot.reply_to(message, 'Corretto!' + '\n' + username + " ha guadagnato 10 punti.", reply_markup=markup)
            answer = ''
            update_points(message,user_id, 10, username, correct=True)
        else:
            bot.reply_to(message, 'Errato! La risposta corretta è ' + answer.replace('_', ' ') + '.\n' + username + " ha perso 10 punti.", reply_markup=markup)
            answer = ''
            update_points(message,user_id, -10, username, wrong=True)
        if quiz_id:
            try:
                bot.delete_message(message.chat.id, quiz_id)
            except:
                pass
    else:
        bot.reply_to(message, 'Hai già risposto a questo quiz!\nSmettila di provare a imbrogliare!!')
    quiz_id = None
    chat_quiz_id = None
    
#-----------------------------------------------------------------------------------------
#   ____       _      _   _   ____     ___    __  __ 
#  |  _ \     / \    | \ | | |  _ \   / _ \  |  \/  |
#  | |_) |   / _ \   |  \| | | | | | | | | | | |\/| |
#  |  _ <   / ___ \  | |\  | | |_| | | |_| | | |  | |
#  |_| \_\ /_/   \_\ |_| \_| |____/   \___/  |_|  |_|
#-----------------------------------------------------------------------------------------

@bot.message_handler(commands=['random'])
def random_(message):
    randoms:Collection[Random]=db["randoms"] 
    doc=randoms.find_one({"server_id":message.chat.id})
    if doc is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return
    bot.reply_to(message,random.choice(doc["randoms"]))

@bot.message_handler(commands=['add_random'])
def add_random(message):
    global length
    text = get_text(message.text)
    
    if text=='': return bot.reply_to(message, 'Inserire un messaggio.')

    randoms:Collection[Random]=db["randoms"] 
    doc=randoms.find_one_and_update({"server_id":message.chat.id},{"$addToSet":{"randoms":text}},return_document=ReturnDocument.BEFORE)
    if doc is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return
    doc_after=randoms.find_one({"server_id":message.chat.id})

    if doc_after != doc:
        bot.reply_to(message, 'Aggiunto!')
    else: 
        bot.reply_to(message, 'Questa frase è già stata inserita!')

@bot.message_handler(commands=['rm_random'])
def rm_random(message):
    if not message.reply_to_message:
        text = get_text(message.text).strip()
        if text != '':
            frase_to_remove = text
        else:
            bot.reply_to(message, "Inserire una frase da rimuove o rispondere ad un messaggio che ne contiene una.")
            return
        
    elif message.reply_to_message.text and message.reply_to_message.text.startswith('/add_random'):
        frase_to_remove = get_text(message.reply_to_message.text)
    else:
        frase_to_remove = message.reply_to_message.text

    if not frase_to_remove:
        bot.reply_to(message, "Inserire una frase da rimuove o ripsondere ad un messaggio che ne contiene una.")
        return 

    randoms:Collection[Random]=db["randoms"]
    before=randoms.find_one({"server_id":message.chat.id})
    if before is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return
    doc=randoms.find_one_and_update({"server_id":message.chat.id},{"$pull":{"randoms":frase_to_remove}},return_document=ReturnDocument.AFTER)
    
    if doc!=before:
        bot.reply_to(message, f"Frase rimossa:\n{frase_to_remove}")
    else: 
        bot.reply_to(message, f"Frase non trovata:\n{frase_to_remove}")


#-----------------------------------------------------------------------------------------
#    ___    ____       _      ____     ____    ___    ____    _____ 
#   / _ \  |  _ \     / \    / ___|   / ___|  / _ \  |  _ \  | ____|
#  | | | | | |_) |   / _ \   \___ \  | |     | | | | | |_) | |  _|  
#  | |_| | |  _ <   / ___ \   ___) | | |___  | |_| | |  _ <  | |___ 
#   \___/  |_| \_\ /_/   \_\ |____/   \____|  \___/  |_| \_\ |_____|
#-----------------------------------------------------------------------------------------

def get_orascore(server_id:int,user_id:int|str):

    oracoin:Collection[Oracoin]=db["oracoin"]
    doc=oracoin.find_one({"server_id":server_id})
   
    if doc is None: return 0

    return doc["data"][str(user_id)]["oracoins"] if doc["data"].get(str(user_id)) else 0


@bot.message_handler(commands=['tutorial_poll'])
def tutorial(message):
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    tuto = (
        f"Benvenuto {username} nel sistema polymarket di Orabot!\n"
        f"I tuoi punti sono Oracoins che puoi utilizzare per comprare quote nei sondaggi con /bet.\n"
        f"Il prezzo di ogni quota di un'opzione è definito dal (rapporto tra numero di quote di quell'opzione e numero di quote totali del sondaggio) * 100.\n"
        f"Inoltre, puoi creare tu stesso dei sondaggi con /poll.\n"
        f"Una volta creato un sondaggio, esso rimarrà aperto fino al momento della chiusura.\n"
        f"Per chiudere un sondaggio usa /solve_poll.\n"
        f"Quando si chiude un sondaggio verrà distribuito 100 Oracoins per ogni quota vincente.\n"
        f"Per sapere quali sondaggi sono attivi in questo momento utilizza /active_polls.\n"
        f"Se sei curioso di sapere la classifica del server usa /orascore."
    )
    bot.reply_to(message, tuto)

@bot.message_handler(commands=['poll'])
def poll(message):
    polymarket:Collection[Polymarket]=db["polymarket"]
    doc_polymarket=polymarket.find_one({"server_id":message.chat.id})
    if doc_polymarket is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return 
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    chat_id = message.chat.id

    # Formato: /creasondaggio "Domanda?" "Opzione 1" "Opzione 2" ...
    if message.text == "":
        bot.reply_to(message, "Inserire una domanda e almeno due risposte nel seguente formato:\n/poll \"domanda\" \"opzione 1\" \"opzione 2\" ...")
        return
    parts = message.text.split('"')[1::2]
    if len(parts) < 3:
        bot.reply_to(message, "Inserire una domanda e almeno due risposte nel seguente formato:\n/poll \"domanda\" \"opzione 1\" \"opzione 2\" ...")
        return
    question = parts[0]
    options = parts[1:]
    
    if len(options) < 2:
        bot.reply_to(message, "Devi fornire almeno 2 opzioni.")
        return
        
    poll = bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=False,
        reply_to_message_id=message.id
    )

    quotes = []
    for _ in range(len(options)): 
        quotes.append(1)
   
    
    new_poll=Poll(
        creator_id=user_id,
        creator_username=username,
        question=question,
        options=options,
        quotes=quotes,
        bets=[]
    )
    
    polymarket.update_one({"server_id":message.chat.id},{"$set":{f"polls.{poll.id}":new_poll}})
    bot.reply_to(poll, f"Poll_id: {poll.id}")
                

@bot.message_handler(commands=['bet'])
def place_bet(message):
    polymarket:Collection[Polymarket]=db["polymarket"]
    doc_polymarket=polymarket.find_one({"server_id":message.chat.id})
    if doc_polymarket is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return
    oracoin:Collection[Oracoin]=db["oracoin"]
    doc_oracoin=oracoin.find_one({"server_id":message.chat.id})
    if doc_oracoin is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return


    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    
    # Formato: /scommetti <poll_id> <option_num> <quotes_num>
    parts = message.text.split()
    if len(parts) < 4:
        bot.reply_to(message, "Inserire la propria scomessa nel seguente formato: /bet <poll_id> <option_num> <quotes_num>")
        return
        
    poll_id = parts[1]
    option_id = int(parts[2])
    quotes = int(parts[3])
    current_points = get_orascore(message.chat.id,user_id)
        
    poll=doc_polymarket["polls"].get(poll_id,None)

    if not poll:
        bot.reply_to(message, "Sondaggio non trovato.")
        return
        
    if user_id == poll["creator_id"]:
        bot.reply_to(message, "Sei tu il creatore di questo sondaggio!")
        return
    
    if option_id < 0 or option_id >= len(poll["options"]):
        bot.reply_to(message, "Opzione non valida.")
        return
    
    pricepq = (poll["quotes"][option_id]/sum(poll["quotes"]))*100
    pricet = quotes*pricepq
    if quotes <= 0:
        bot.reply_to(message, "Per il momento non si possono ancora vendere quote.")
        return
    
    if current_points < pricet:
        bot.reply_to(message, f"Non hai abbastanza Oracoins, povero! Hai solo {current_points} Oracoins.")
        return
        
    oracoin.update_one({"server_id":message.chat.id},{"$inc":{f"data.{user_id}.oracoins":-round(pricet),f"data.{user_id}.locked_points":round(pricet)}})

    quotesdb = poll["quotes"]
    quotesdb_togo = quotesdb
    quotesdb_togo[option_id] += quotes
    polymarket.update_one({"server_id":message.chat.id},{"$set":{f"polls.{poll_id}.quotes":quotesdb_togo}})
    
    bet=Bet(
        user_id=user_id,
        option_id=option_id,
        amount=round(pricet),
        quotes=quotes
    )
    polymarket.update_one({"server_id":message.chat.id},{"$push":{f"polls.{poll_id}.bets":bet}})

    option_text = poll["options"][option_id]
    bot.reply_to(message, f"{username} ha scommesso {round(pricet)} Oracoins sull'opzione {option_id}: {option_text} del sondaggio con id: {poll_id}!")
            

@bot.message_handler(commands=['solve_poll'])
def resolve_poll(message):
    polymarket:Collection[Polymarket]=db["polymarket"]
    doc_polymarket=polymarket.find_one({"server_id":message.chat.id})
    if doc_polymarket is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return
    oracoin:Collection[Oracoin]=db["oracoin"]
    doc_oracoin=oracoin.find_one({"server_id":message.chat.id})
    if doc_oracoin is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return



    # FORMATO: /risultato <poll_id> <winning_option_num>
    if get_text(message.text).strip() == "":
        bot.reply_to(message, "Inserire la solve del sondaggio nel seguente formato: /solve <poll_id> <winning_option_num>")
        return
    
    parts = get_text(message.text).split()
    if len(parts) != 2:
        bot.reply_to(message, "Inserire la solve del sondaggio nel seguente formato: /solve <poll_id> <winning_option_num>")
        return
    poll_id = get_text(message.text).split()[0]
    try:
        winning_option = int(get_text(message.text).split()[1])
    except ValueError:
        bot.reply_to(message, "L'opzione vincente deve essere un numero!")
        return
    user_id = message.from_user.id
    


    poll_id = parts[0]

    poll = doc_polymarket["polls"][poll_id] 

    
    if not poll:
        bot.reply_to(message, "Sondaggio non trovato o già risolto!")
        return
    
    if user_id != poll["creator_id"]:
        bot.reply_to(message, f"Non sei tu il creatore di questo sondaggio!\nIl creatore è {poll["creator_username"]}")
        return
        
    if winning_option < 0 or winning_option >= len(poll["options"]):
        bot.reply_to(message, "Opzione non valida!")
        return
    winning_text = poll["options"][winning_option]   


    bets = poll["bets"]
    
        
    for bet in bets:
        if bet["option_id"] == winning_option:
            win_amount = round(bet["quotes"]*100)
            oracoin.update_one({"server_id":message.chat.id},{"$inc":{f"data.{bet["user_id"]}.oracoins":win_amount,f"data.{bet["user_id"]}.locked_points":-bet["amount"]}})
            
        else:
            oracoin.update_one({"server_id":message.chat.id},{"$inc":{f"data.{bet["user_id"]}.locked_points":-bet["amount"]}})

    polymarket.update_one({"server_id":message.chat.id},{"$unset":{f"polls.{poll_id}":""}})
    
    
    result_text = (
        f"Sondaggio chiuso!\n"
        f"Opzione vincente: {winning_option}: {winning_text}\n"
    )
    bot.reply_to(message, result_text) 

@bot.message_handler(commands=['orascore'])
def orascore(message):

    oracoin:Collection[Oracoin]=db["oracoin"] 
    doc=oracoin.find_one({"server_id":message.chat.id})
    if doc is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return
    rows=[]
    for _,x in doc["data"].items():
        rows.append((x["oracoins"],x["username"]))
    rows=sorted(rows,reverse=True)
    rows=rows[:12]
    try:
        ranking = "Classifica Oracoins:\n--------------------------\n"
        for points,username in rows:
            ranking += f"{username or 'Utente'}: {points}\n"

        bot.reply_to(message, ranking if rows else 'Nessun utente trovato.')
    finally:
        pass


@bot.message_handler(commands=['active_polls'])
def active_polls(message):
    polymarket:Collection[Polymarket]=db["polymarket"]
    doc_polymarket=polymarket.find_one({"server_id":message.chat.id})
    if doc_polymarket is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return

    actives = "Sondaggi ancora aperti:\n------------------------------------\n"
    polls = doc_polymarket["polls"]

    if not polls:
        bot.reply_to(message, "Nessun sondaggio attivo al momento.")
        return
    for poll_id, poll in polls.items():
        actives += f"Sondaggio: {poll_id}\nCreato da: {poll["creator_username"]}\nDomanda: {poll["question"]}\n"
        table = []
        headers = ["Opzioni", "%"]
        for i in range(len(poll["options"])):
            option = []
            perc = 0
            if sum(poll["quotes"]) != 0:
                perc = int(poll["quotes"][i]/sum(poll["quotes"])*100)
            option.append(poll["options"][i][:10])
            option.append(f"{perc}")
            table.append(option)
        actives += f"`{tabulate.tabulate(table, headers, tablefmt="simple")}`\n------------------------------------\n"
    print(actives)
    bot.reply_to(message, escape_markdown_v2(actives), parse_mode='MarkdownV2')
    
#-----------------------------------------------------------------------------------------
#   _____   _          _       ____   _       _____ 
#  |  ___| | |        / \     / ___| | |     | ____|
#  | |_    | |       / _ \   | |  _  | |     |  _|  
#  |  _|   | |___   / ___ \  | |_| | | |___  | |___ 
#  |_|     |_____| /_/   \_\  \____| |_____| |_____|
#-----------------------------------------------------------------------------------------



def download_flag(nazione, larghezza=1200):
    nazione = nazione.capitalize()
    if nazione in map_flags:
        nazione = map_flags[nazione]
        nome_file = "Flag_of_" + "_".join(word for word in nazione.split()) + ".svg"
    else:
        nome_file = "Flag_of_" + "_".join(word.capitalize() for word in nazione.split()) + ".svg"
    nome_file_encoded = urllib.parse.quote(nome_file)
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        url_api = f"https://commons.wikimedia.org/w/api.php?action=query&titles=File:{nome_file_encoded}&prop=imageinfo&iiprop=url&format=json"
        response = requests.get(url_api, headers=headers)
        response.raise_for_status()
        data = response.json()

        pagina = next(iter(data["query"]["pages"].values()))
        imageinfo = pagina.get("imageinfo")
        if not imageinfo:
            raise ValueError(f"Bandiera non trovata: {nazione}")

        url_base = imageinfo[0]["url"].replace("/commons/", "/commons/thumb/").split(".svg")[0]
        url_finale = f"{url_base}.svg/{larghezza}px-{nome_file_encoded}.png"

        r = requests.get(url_finale, headers=headers)
        r.raise_for_status()
        img= Image.open(BytesIO(r.content)).convert('RGB')

        return img

    except Exception as e:
        print(f"Errore per '{nazione}': {str(e)}")
        return None

def flag_and(img1, img2):
    arr1 = np.array(img1)
    arr2 = np.array(img2.resize(img1.size))
    
    mask = np.all(arr1 == arr2, axis=-1)
    
    result = np.where(mask[..., None], arr1, 0)
    
    output_buffer = BytesIO()
    Image.fromarray(result).save(output_buffer, format='PNG')
    output_buffer.seek(0)
    
    return output_buffer

def colori_simili(c1, c2, tolleranza=60):
    return np.sqrt(np.sum((np.array(c1) - np.array(c2)) ** 2)) < tolleranza

def update_flag_progress(original, progress, guess_img, tolleranza=30):
    original_arr = np.array(original, dtype=np.float32)
    guess_arr = np.array(guess_img.resize(original.size), dtype=np.float32)
    progress_arr = np.array(progress, dtype=np.uint8)
    try:
        diff = np.sqrt(np.sum((original_arr - guess_arr) ** 2, axis=-1))
    except Exception as e:
        print(f"Errore nel calcolo della differenza: {e}")
        return BytesIO()

    mask = diff < tolleranza
    
    current_matches = np.any(progress_arr != [0, 0, 0], axis=-1)
    combined_matches = mask | current_matches

    result = np.where(combined_matches[..., None], original_arr, [0, 0, 0]).astype(np.uint8)

    output_buffer = BytesIO()
    Image.fromarray(result).save(output_buffer, format='PNG')
    output_buffer.seek(0)

    return output_buffer

#
flagle_sessions = {}

def init_flagle_session(chat_id, starter_id, starter_username, secret_flag, secret_flag_original, secret_flag_progress):
    flagle_sessions[chat_id] = {
        "starter_id": starter_id,
        "starter_username": starter_username,
        "secret_flag": secret_flag,
        "secret_flag_original": secret_flag_original,
        "secret_flag_progress": secret_flag_progress,
        "flagled_done": [],
        "last_flagled": None,
        "flag_id": None,
        "chat_flag_id": None,
        "flagling": True
    }

def get_session(chat_id):
    return flagle_sessions.get(chat_id)

def end_session(chat_id):
    flagle_sessions.pop(chat_id, None)


@bot.message_handler(commands=['flagle'])
def flagle(message):
    oracoin: Collection[Oracoin] = db["oracoin"]
    doc = oracoin.find_one({"server_id": message.chat.id})
    if doc is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return

    session = get_session(message.chat.id)
    if session:
        if session["flagling"]:
            bot.reply_to(message, "Un'altra partita di Flagle è già in corso in questa chat.")
            return
        if session["flag_id"] is not None and session["chat_flag_id"] is not None:
                try:
                    bot.delete_message(session["chat_flag_id"], session["flag_id"])
                except:
                    pass
    end_session(message.chat.id)

    starter_id = message.from_user.id
    starter_username = message.from_user.username or message.from_user.first_name or 'Utente'

    secret_flag = random.choice(english_names)
    print(f"[FLAGLE] Bandiera segreta: {secret_flag}")
    secret_flag_original = download_flag(secret_flag)
    if not secret_flag_original:
        bot.reply_to(message, "Errore nel caricamento della bandiera segreta. Riprova.")
        return

    secret_flag_progress = Image.new('RGB', secret_flag_original.size, (0, 0, 0))

    free_flag = secret_flag
    while free_flag == secret_flag:
        free_flag = random.choice(english_names)

    init_flagle_session(message.chat.id, starter_id, starter_username, secret_flag, secret_flag_original, secret_flag_progress)

    bot.reply_to(message,
                 f"Un nuovo game di Flagle è iniziato.\nProva a indovinare la bandiera con /guess <bandiera>\n"
                 f"Avrai un primo aiuto gratis con la bandiera: {italian_names[english_names.index(free_flag)]}.")

    class MockMessage:
        def __init__(self, text, chat_id, message_id, from_user):
            self.text = text
            self.chat = type('Chat', (), {'id': chat_id})
            self.message_id = message_id
            self.from_user = from_user
            self.id = message.id

    mock_msg = MockMessage(
        text=f"/guess {free_flag}",
        chat_id=message.chat.id,
        message_id=message.message_id,
        from_user=message.from_user
    )
    guess(mock_msg, True)


@bot.message_handler(commands=['guess'])
def guess(message, free=False):
    oracoin: Collection[Oracoin] = db["oracoin"]
    doc = oracoin.find_one({"server_id": message.chat.id})
    if doc is None:
        bot.reply_to(message, "Bot non inizializzato in questo server, fai /start")
        return

    session = get_session(message.chat.id)
    if not session or not session["flagling"]:
        bot.reply_to(message, "Nessun game di Flagle in corso.\nIniziane uno con /flagle.")
        return

    username = message.from_user.username or message.from_user.first_name or 'Utente'
    user_id = message.from_user.id
    guessed_flag = get_text(message.text).replace('_', ' ').capitalize().strip()

    if not guessed_flag:
        bot.reply_to(message, "Nessuna bandiera specificata.")
        return

    if guessed_flag in map_guess:
        guessed_flag = map_guess[guessed_flag]
    elif guessed_flag.lower() in italian_names_lower:
        guessed_flag = english_names[italian_names_lower.index(guessed_flag.lower())]
    elif guessed_flag.lower() not in english_names_lower:
        bot.reply_to(message, "Bandiera inesistente!")
        return

    if guessed_flag in session["flagled_done"]:
        bot.reply_to(message, "Questo tentativo è già stato fatto!")
        return
    session["flagled_done"].append(guessed_flag)

    guessed_flag_img = download_flag(guessed_flag)
    if not guessed_flag_img:
        bot.reply_to(message, "Errore nel caricamento della bandiera, riprova.")
        return

    print(f"[FLAGLE] Guess: {guessed_flag}")

    try:
        current_progress = Image.open(session["secret_flag_progress"]) if isinstance(session["secret_flag_progress"], BytesIO) else session["secret_flag_progress"]

        updated_progress = update_flag_progress(session["secret_flag_original"], current_progress, guessed_flag_img)

        session["secret_flag_progress"] = Image.open(updated_progress)
        updated_progress.seek(0)

        if session["flag_id"] is not None and session["chat_flag_id"] is not None:
            try:
                bot.delete_message(session["chat_flag_id"], session["flag_id"])
            except:
                pass

        if guessed_flag == session["secret_flag"]:
            output_buffer = BytesIO()
            session["secret_flag_original"].save(output_buffer, format='PNG')
            output_buffer.seek(0)

            if not free:
                sent_flag = bot.send_photo(message.chat.id, output_buffer,
                                           caption=f"Corretto!\n{username} ha guadagnato 50 Oracoin!",
                                           reply_to_message_id=message.id)
                update_points(message, user_id, 50, username)
            else:
                sent_flag = bot.send_photo(message.chat.id, output_buffer,
                                           caption=f"La risposta corretta era: {session['secret_flag']}, scarsi!\n"
                                                   f"{session['starter_username']} ha perso 20 Oracoin!",
                                           reply_to_message_id=message.id)
                update_points(message, session["starter_id"], -20, session["starter_username"])
            
            session["flagling"] = False
        elif not free:
            sent_flag = bot.send_photo(message.chat.id, updated_progress,
                                       caption=f"Errato! {username} ha perso 7 Oracoin!\nProgresso corrente:",
                                       reply_to_message_id=message.id)
            update_points(message, user_id, -7, username)
        else:
            sent_flag = bot.send_photo(message.chat.id, updated_progress,
                                       caption=f"Progresso corrente:",
                                       reply_to_message_id=message.id)

        buffer = BytesIO()
        if isinstance(updated_progress, BytesIO):
            updated_progress.seek(0)
            img = Image.open(updated_progress)
        else:
            img = updated_progress
        img.save(buffer, format='PNG')
        buffer.seek(0)
        session["last_flagled"] = buffer

        session["flag_id"] = sent_flag.message_id
        session["chat_flag_id"] = sent_flag.chat.id

    except Exception as e:
        print(f"Errore durante l'aggiornamento del progresso: {str(e)}")
        bot.reply_to(message, "Si è verificato un errore durante l'elaborazione. Riprova.")


@bot.message_handler(commands=['arrendo'])
def arrendo(message):
    session = get_session(message.chat.id)
    if not session or not session["flagling"]:
        bot.reply_to(message, "Nessuna partita in corso!")
        return
    if session["flag_id"] is not None and session["chat_flag_id"] is not None:
        try:
            bot.delete_message(session["chat_flag_id"], session["flag_id"])
        except:
            pass

    if message.from_user.id == session["starter_id"]:
        output_buffer = BytesIO()
        session["secret_flag_original"].save(output_buffer, format='PNG')
        output_buffer.seek(0)
        sent_flag = bot.send_photo(message.chat.id, output_buffer,
                       caption=f"La risposta corretta era: {session['secret_flag']}, scarsi!\n"
                               f"{session['starter_username']} ha perso 20 Oracoin!")
        update_points(message, session["starter_id"], -20, session["starter_username"])
        session["flagling"] = False
        session["flag_id"] = sent_flag.message_id
        session["chat_flag_id"] = sent_flag.chat.id
    else:
        bot.reply_to(message, f"Solo {session['starter_username']} può decidere di arrendersi!")


@bot.message_handler(commands=['flagled'])
def flagled(message):
    session = get_session(message.chat.id)
    if not session or not session["flagling"]:
        bot.reply_to(message, "Nessuna partita di Flagle in corso!")
        return

    if session["flag_id"] is not None and session["chat_flag_id"] is not None:
        try:
            bot.delete_message(session["chat_flag_id"], session["flag_id"])
        except:
            pass

    msg = "Ecco la lista di tutti i tentativi già fatti:\n"
    for guess in session["flagled_done"]:
        if guess.lower() in english_names_lower:
            guess = italian_names[english_names_lower.index(guess.lower())]
        else:
            continue
        msg += f"{guess}\n"

    if session["last_flagled"]:
        session["last_flagled"].seek(0)
        sent_flag = bot.send_photo(message.chat.id, session["last_flagled"], caption=msg, reply_to_message_id=message.id)
        session["flag_id"] = sent_flag.message_id
        session["chat_flag_id"] = sent_flag.chat.id
    else:
        bot.reply_to(message, "Nessuna immagine di progresso disponibile.")


bot.infinity_polling()
