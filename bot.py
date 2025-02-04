import json
import os
import psycopg2
import random
import requests
import telebot

from johnson import johnson_image

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

db = os.environ.get('DB')
host = os.environ.get('DB_HOST')
user = os.environ.get('DB_USER')
pwd = os.environ.get('DB_PASSWORD')

started = False
answer = ''

def get_text(message):
    words = message.replace('\n', ' \n').split()
    return ' '.join(words[1:])

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, '...')

@bot.message_handler(commands=['ciao'])
def ciao(message):
    bot.reply_to(message, 'Buondì!')

@bot.message_handler(commands=['ora'])
def ora(message):
    bot.reply_to(message, 'A che ora è mate?')

@bot.message_handler(commands=['johnson'])
def johnson(message):
    solid = random.choice(johnson_image).capitalize()
    bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + solid + '.png', solid.replace('_', ' '), reply_to_message_id=message.id)

@bot.message_handler(commands=['random'])
def random_(message):
    with psycopg2.connect(host=host, database=db, user=user, password=pwd) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT frase FROM random ORDER BY RANDOM() LIMIT 1')
            bot.reply_to(message, cur.fetchone())

@bot.message_handler(commands=['add_random'])
def add_random(message):
    global length
    text = get_text(message.text)

    if text != '':
        with psycopg2.connect(host=host, database=db, user=user,password=pwd) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute('INSERT INTO random (frase) VALUES (%s)', (text,))
                    bot.reply_to(message, 'Aggiunto!')
                except:
                    bot.reply_to(message, 'Questa frase è già stata inserita!')
    else:
        bot.reply_to(message, 'Inserire un messaggio.')

@bot.message_handler(commands=['quiz'])
def quiz(message):
    global answer
    options = random.sample(johnson_image, 3)
    answer = random.choice(options).replace('_', ' ')

    markup = telebot.types.ReplyKeyboardMarkup()
    for item in options:
        markup.row(telebot.types.KeyboardButton('/ans ' + item.replace('_', ' ')))

    bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + answer.capitalize() + '.png', 'Che solido di Johnson è?', reply_to_message_id=message.id, reply_markup=markup)

@bot.message_handler(commands=['ans'])
def ans(message):
    global answer

    if answer == '':
        bot.reply_to(message, 'Nessun quiz in corso. Per avviarne uno usa /quiz.')
    else:
        markup = telebot.types.ReplyKeyboardRemove(selective=False)
        if get_text(message.text) == answer:
            bot.reply_to(message, 'Corretto!', reply_markup=markup)
        else:
            bot.reply_to(message, 'Errato! La risposta corretta è ' + answer.replace('_', ' ') + '', reply_markup=markup)
        answer = ''

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
        # bot.send_document(message.chat.id, link, message.id, name + '\n' + tl + '\n' + ml)
    else:
        bot.reply_to(message, 'Nome del problema sbagliato. Riprovare.')

bot.infinity_polling()
