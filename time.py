import sys, getopt, sqlite3, datetime, re, json, os

usage = 'usage: time.py <command> -m <message> -t <time> -d <date>'

def validate(action, last_action):
    validated = False
    if last_action == None:
        return action == 'start'
    else:
        return last_action[0] in {
            'start': ('stop', ),
            'stop': ('start', 'lunch', 'coffee', 'resume'),
            'lunch': ('start', 'coffee', 'resume'),
            'coffee': ('start', 'lunch', 'resume'),
            'resume': ('lunch', 'coffee')
        }[action]

def get_last_action(retro, cursor):
    cursor.execute('SELECT action, time FROM Actions WHERE date = ? ORDER BY time DESC LIMIT 1;', [retro['date']])
    last_action = cursor.fetchone()
    if last_action != None:
        if minutes_between(last_action[1], retro['time']) < 0:
            print('Cannot insert actions between already logged actions.')
            sys.exit(9)
    return last_action

def insert_action(params):
    cursor.execute('INSERT INTO Actions (action, date, time, message) VALUES (:action, :date, :time, :message)', params)

def start(params):
    if not validate('start', params['last_action']):
        print('Cannot start work day when already working. To resume after break, use resume instead.')
        sys.exit(8)
    insert_action({
        'action': 'start',
        'date': params['retro']['date'],
        'time': params['retro']['time'],
        'message': params['message']
    })
    status(params)

def stop(params):
    if not validate('stop', params['last_action']):
        print('Cannot stop before starting.')
        sys.exit(8)
    insert_action({
        'action': 'stop',
        'date': params['retro']['date'],
        'time': params['retro']['time'],
        'message': params['message']
    })
    status(params)

def lunch(params):
    if not validate('lunch', params['last_action']):
        print('Cannot start lunch break when not working.')
        sys.exit(8)
    insert_action({
        'action': 'lunch',
        'date': params['retro']['date'],
        'time': params['retro']['time'],
        'message': params['message']
    })
    status(params)

def coffee(params):
    if not validate('coffee', params['last_action']):
        print('Cannot start coffee break when not working.')
        sys.exit(8)
    insert_action({
        'action': 'coffee',
        'date': params['retro']['date'],
        'time': params['retro']['time'],
        'message': params['message']
    })
    status(params)

def resume(params):
    if not validate('resume', params['last_action']):
        print('Cannot resume work when not on a break.')
        sys.exit(8)
    insert_action({
        'action': 'resume',
        'date': params['retro']['date'],
        'time': params['retro']['time'],
        'message': params['message']
    })
    status(params)
    
def status(params):
    cursor.execute('SELECT action, time, message FROM Actions WHERE date = :date;', { 'date': params['retro']['date'] })
    today_actions = cursor.fetchall()
    current_state = None
    last_time = None
    cumulative = {
        'work': 0,
        'break': 0,
        'lunch': 0
    }
    for action, time, message in today_actions:
        if current_state != None:
            cumulative[current_state] += minutes_between(last_time, time)
        current_state = {
            'start': 'work',
            'lunch': 'lunch',
            'coffee': 'break',
            'resume': 'work',
            'stop': None
        }[action]
        last_time = time
    if current_state != None:
        cumulative[current_state] += minutes_between(last_time, str(datetime.datetime.now().time())[0:5])
    print('======== TODAY ========')
    paid_hours, paid_minutes = hours_and_minutes(cumulative['work'] + cumulative['break'])
    print('paid time: {} h {} min'.format(paid_hours, paid_minutes))
    break_hours, break_minutes = hours_and_minutes(cumulative['break'])
    print('of which {} h {} min was break-time.'.format(break_hours, break_minutes))
    lunch_hours, lunch_minutes = hours_and_minutes(cumulative['lunch'])
    print('unpaid lunch time: {} h {} min.'.format(lunch_hours, lunch_minutes))
    stateStr = {
        None: 'not working',
        'work': 'working',
        'lunch': 'on lunch break',
        'break': 'on break'
    }
    print('currently {}.'.format(stateStr[current_state]))

def average(params):
    current_date = None
    current_state = None
    last_time = None
    days = 0
    cumulative = {
        'work': 0,
        'break': 0,
        'lunch': 0
    }
    today = {
        None: 0,
        'work': 0,
        'break': 0,
        'lunch': 0
    }
    for action in cursor.execute('SELECT action, time FROM Actions;'):
        if action[0] == 'start':
            today = {
                None: 0,
                'work': 0,
                'break': 0,
                'lunch': 0
            }
        if last_time != None:
            today[current_state] += minutes_between(last_time, action[1])
        if action[0] == 'stop':
            days += 1
            for key in cumulative:
                cumulative[key] += today[key]
        current_state = {
            'start': 'work',
            'lunch': 'lunch',
            'coffee': 'break',
            'resume': 'work',
            'stop': None
        }[action[0]]
        last_time = action[1]
    print('======== AVERAGE ========')
    if days == 0:
        print('No days logged.')
        return
    print('days logged: {}'.format(days))
    paid_hours, paid_minutes = hours_and_minutes((cumulative['work'] + cumulative['break']) / days)
    print('paid time: {} h {} min'.format(paid_hours, paid_minutes))
    break_hours, break_minutes = hours_and_minutes(cumulative['break'] / days)
    print('of which {} h {} min was break-time.'.format(break_hours, break_minutes))
    lunch_hours, lunch_minutes = hours_and_minutes(cumulative['lunch'] / days)
    print('unpaid lunch time: {} h {} min.'.format(lunch_hours, lunch_minutes))
    
def minutes_between(start, stop):
    hours_start, minutes_start = map(lambda x: int(x), start.split(':'))
    hours_stop, minutes_stop = map(lambda x: int(x), stop.split(':'))
    return (hours_stop - hours_start) * 60 + (minutes_stop - minutes_start)

def hours_and_minutes(minutes):
    return (int(minutes / 60), minutes % 60)

def setup():
    connection = sqlite3.connect('time.db')
    cursor = connection.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS Actions (id INTEGER PRIMARY KEY AUTOINCREMENT, action VARCHAR(6) NOT NULL, time VARCHAR(5) NOT NULL, date VARCHAR(10) NOT NULL, message TEXT);')
    return (connection, cursor)

def parse_date(date):
    day, month, year = date.split(':')
    return '{}-{}-{}'.format(year, month, day)

def parse_time(time):
    hour, minute = time.split(':')
    if len(hour) == 1:
        hour = '0' + hour
    return '{}:{}'.format(hour, minute)

def main(argv, cursor):
    try:
        opts, args = getopt.getopt(argv, 'm:t:d:', ['message=', 'time=', 'date='])
    except getopt.GetoptError:
        print(usage)
        sys.exit(2)
    message = None
    retro_time = None
    retro_date = None
    for opt, arg in opts:
        if opt == '-h':
            print(usage)
            sys.exit(0)
        elif opt in ('-m', '--message'):
            message = arg
        elif opt in ('-t', '--time'):
            retro_time = arg
        elif opt in ('-d', '--date'):
            retro_date = arg
    if len(args) > 1:
        print(usage)
        sys.exit(3)
    if len(args) == 0:
        command = 'status'
    else:
        command = args[0]
    if command not in ('start', 'stop', 'lunch', 'coffee', 'resume', 'status', 'break', 'continue', 'average'):
        print('Unknown command. Command must be one of start, stop, lunch, coffee, resume, status, average')
        sys.exit(4)
    retro = {}
    if retro_date != None:
        try:
            retro['date'] = parse_date(retro_date)
        except:
            print('Could not parse date. Date should be dd:mm:yyyy')
            sys.exit(5)
        if retro_time == None:
            print('Cannot have retroactive date without retroactive time. Set the time with -t <time>')
            sys.exit(7)
    else: 
        retro['date'] = str(datetime.datetime.now().date())
    if retro_time != None:
        try:
            retro['time'] = parse_time(retro_time)
        except:
            print('Could not parse time. Time should be hh:mm')
            sys.exit(6)
    else:
        retro['time'] = str(datetime.datetime.now().time())[:5]
    last_action = get_last_action(retro, cursor)
    params = {
        'last_action': last_action,
        'message': message,
        'retro': retro,
        'cursor': cursor
    }
    {
        'start': start,
        'stop': stop,
        'lunch': lunch,
        'coffee': coffee,
        'break': coffee,
        'resume': resume,
        'continue': resume,
        'status': status,
        'average': average
    }[command](params)

if __name__ == "__main__":
    connection, cursor = setup()
    main(sys.argv[1:], cursor)
    connection.commit()
    connection.close()
