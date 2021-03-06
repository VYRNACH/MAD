# -*- coding: utf-8 -*-
import sys

from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper

sys.path.append("..")  # Adds higher directory to python modules path.

import threading
import logging
import time
from flask import (Flask, jsonify, render_template,
                   request, send_from_directory, redirect)
from flask_caching import Cache
from utils.walkerArgs import parseArgs
import json
import os, glob, platform
import re
import datetime
from shutil import copyfile
from math import floor

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

log = logging.getLogger(__name__)

args = parseArgs()

if args.db_method == "rm":
    db_wrapper = RmWrapper(args, None)
elif args.db_method == "monocle":
    db_wrapper = MonocleWrapper(args, None)
else:
    log.error("Invalid db_method in config. Exiting")
    sys.exit(1)


# @app.before_first_request
# def init():
#     task = my_task.apply_async()
def run_job():
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        exit(0)

    t_webApp = threading.Thread(name='Web App', target=run_job)
    t_webApp.setDaemon(True)
    t_webApp.start()


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/screens', methods=['GET'])
def screens():
    return render_template('screens.html', responsive=str(args.madmin_noresponsive).lower())


@app.route('/', methods=['GET'])
def root():
    return render_template('index.html')


@app.route('/raids', methods=['GET'])
def raids():
    return render_template('raids.html', sort=str(args.madmin_sort), responsive=str(args.madmin_noresponsive).lower())


@app.route('/gyms', methods=['GET'])
def gyms():
    return render_template('gyms.html', sort=args.madmin_sort, responsive=str(args.madmin_noresponsive).lower())


@app.route('/unknown', methods=['GET'])
def unknown():
    return render_template('unknown.html', responsive=str(args.madmin_noresponsive).lower())


@app.route('/map', methods=['GET'])
def map():
    return render_template('map.html')


@app.route("/submit_hash")
def submit_hash():
    hash = request.args.get('hash')
    id = request.args.get('id')

    if db_wrapper.insert_hash(hash, 'gym', id, '999', unique_hash="madmin"):

        for file in glob.glob("www_hash/unkgym_*" + str(hash) + ".jpg"):
            copyfile(file, 'www_hash/gym_0_0_' + str(hash) + '.jpg')
            os.remove(file)

        return redirect("/unknown", code=302)


@app.route("/modify_raid_gym")
def modify_raid_gym():
    hash = request.args.get('hash')
    id = request.args.get('id')
    mon = request.args.get('mon')
    lvl = request.args.get('lvl')

    newJsonString = encodeHashJson(id, lvl, mon)
    db_wrapper.delete_hash_table('"' + str(hash) + '"', 'raid', 'in', 'hash')
    db_wrapper.insert_hash(hash, 'raid', newJsonString, '999', unique_hash="madmin")

    return redirect("/raids", code=302)


@app.route("/modify_raid_mon")
def modify_raid_mon():
    hash = request.args.get('hash')
    id = request.args.get('gym')
    mon = request.args.get('mon')
    lvl = request.args.get('lvl')

    newJsonString = encodeHashJson(id, lvl, mon)
    db_wrapper.delete_hash_table('"' + str(hash) + '"', 'raid', 'in', 'hash')
    db_wrapper.insert_hash(hash, 'raid', newJsonString, '999', unique_hash="madmin")

    return redirect("/raids", code=302)


@app.route("/modify_gym_hash")
def modify_gym_hash():
    hash = request.args.get('hash')
    id = request.args.get('id')

    db_wrapper.delete_hash_table('"' + str(hash) + '"', 'gym', 'in', 'hash')
    db_wrapper.insert_hash(hash, 'gym', id, '999', unique_hash="madmin")

    return redirect("/gyms", code=302)


@app.route("/near_gym")
def near_gym():
    nearGym = []
    with open('gym_info.json') as f:
        data = json.load(f)
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if lat == "9999":
        distance = int(9999)
        lat = args.home_lat
        lon = args.home_lng
    else:
        distance = int(args.unknown_gym_distance)

    if not lat or not lon:
        return 'Missing Argument...'
    closestGymIds = db_wrapper.get_near_gyms(lat, lon, 123, 1, int(distance), unique_hash="madmin")
    for closegym in closestGymIds:

        gymid = str(closegym[0])
        dist = str(closegym[1])
        gymImage = 'ocr/gym_img/_' + str(gymid) + '_.jpg'

        name = 'unknown'
        lat = '0'
        lon = '0'
        url = '0'
        description = ''

        if str(gymid) in data:
            name = data[str(gymid)]["name"].replace("\\", r"\\").replace('"', '')
            lat = data[str(gymid)]["latitude"]
            lon = data[str(gymid)]["longitude"]
            if data[str(gymid)]["description"]:
                description = data[str(gymid)]["description"].replace("\\", r"\\").replace('"', '').replace("\n", "")

        ngjson = ({'id': gymid, 'dist': dist, 'name': name, 'lat': lat, 'lon': lon, 'description': description, 'filename': gymImage, 'dist': dist})
        nearGym.append(ngjson)

    return jsonify(nearGym)


@app.route("/delete_hash")
def delete_hash():
    nearGym = []
    hash = request.args.get('hash')
    type = request.args.get('type')
    redi = request.args.get('redirect')
    if not hash or not type:
        return 'Missing Argument...'

    db_wrapper.delete_hash_table('"' + str(hash) + '"', type, 'in', 'hash')
    for file in glob.glob("www_hash/*" + str(hash) + ".jpg"):
        os.remove(file)

    return redirect('/' + str(redi), code=302)


@app.route("/delete_file")
def delete_file():
    nearGym = []
    hash = request.args.get('hash')
    type = request.args.get('type')
    redi = request.args.get('redirect')
    if not hash or not type:
        return 'Missing Argument...'

    for file in glob.glob("www_hash/*" + str(hash) + ".jpg"):
        os.remove(file)

    return redirect('/' + str(redi), code=302)


@app.route("/get_gyms")
def get_gyms():
    gyms = []
    data = db_wrapper.get_gym_infos()

    hashdata = json.loads(getAllHash('gym'))

    for file in glob.glob("www_hash/gym_*.jpg"):
        unkfile = re.search('gym_(-?\d+)_(-?\d+)_((?s).*)\.jpg', file)
        hashvalue = (unkfile.group(3))

        if str(hashvalue) in hashdata:

            gymid = hashdata[str(hashvalue)]["id"]
            count = hashdata[hashvalue]["count"]
            modify = hashdata[hashvalue]["modify"]

            creationdate = datetime.datetime.fromtimestamp(creation_date(file)).strftime('%Y-%m-%d %H:%M:%S')

            if args.madmin_time == "12":
                creationdate = datetime.datetime.strptime(creationdate, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %I:%M:%S %p')
                modify = datetime.datetime.strptime(modify, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %I:%M:%S %p')

            name = 'unknown'
            lat = '0'
            lon = '0'
            url = '0'
            description = ''

            gymImage = 'ocr/gym_img/_' + str(gymid) + '_.jpg'

            if str(gymid) in data:
                name = data[str(gymid)]["name"].replace("\\", r"\\").replace('"', '')
                lat = data[str(gymid)]["latitude"]
                lon = data[str(gymid)]["longitude"]
                if data[str(gymid)]["description"]:
                    description = data[str(gymid)]["description"].replace("\\", r"\\").replace('"', '').replace("\n", "")

            gymJson = ({'id': gymid, 'lat': lat, 'lon': lon, 'hashvalue': hashvalue, 'filename': file, 'name': name, 'description': description, 'gymimage': gymImage, 'count': count, 'creation': creationdate, 'modify': modify })
            gyms.append(gymJson)

        else:
            log.debug("File: " + str(file) + " not found in Database")
            os.remove(str(file))
            continue

    return jsonify(gyms)


@app.route("/get_raids")
def get_raids():
    raids = []
    eggIdsByLevel = [1, 1, 2, 2, 3]

    data = db_wrapper.get_gym_infos()

    with open('pokemon.json') as f:
        mondata = json.load(f)

    hashdata = json.loads(getAllHash('raid'))

    for file in glob.glob("www_hash/raid_*.jpg"):
        unkfile = re.search('raid_(-?\d+)_(-?\d+)_((?s).*)\.jpg', file)
        hashvalue = (unkfile.group(3))

        if str(hashvalue) in hashdata:
            monName = 'unknown'
            raidjson = hashdata[str(hashvalue)]["id"]
            count = hashdata[hashvalue]["count"]
            modify = hashdata[hashvalue]["modify"]

            raidHash_ = decodeHashJson(raidjson)
            gymid = raidHash_[0]
            lvl = raidHash_[1]
            mon = int(raidHash_[2])
            monid = int(raidHash_[2])
            mon = "%03d" % mon

            if mon == '000':
                type = 'egg'
                monPic = ''
            else:
                type = 'mon'
                monPic = '/asset/pokemon_icons/pokemon_icon_' + mon + '_00.png'
                if str(monid) in mondata:
                    monName = mondata[str(monid)]["name"]

            eggId = eggIdsByLevel[int(lvl) - 1]
            if eggId == 1:
                eggPic = '/asset/static_assets/png/ic_raid_egg_normal.png'
            if eggId == 2:
                eggPic = '/asset/static_assets/png/ic_raid_egg_rare.png'
            if eggId == 3:
                eggPic = '/asset/static_assets/png/ic_raid_egg_legendary.png'

            creationdate = datetime.datetime.fromtimestamp(creation_date(file)).strftime('%Y-%m-%d %H:%M:%S')

            if args.madmin_time == "12":
                creationdate = datetime.datetime.strptime(creationdate, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %I:%M:%S %p')
                modify = datetime.datetime.strptime(modify, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %I:%M:%S %p')

            name = 'unknown'
            lat = '0'
            lon = '0'
            url = '0'
            description = ''

            gymImage = 'ocr/gym_img/_' + str(gymid) + '_.jpg'

            if str(gymid) in data:
                name = data[str(gymid)]["name"].replace("\\", r"\\").replace('"', '')
                lat = data[str(gymid)]["latitude"]
                lon = data[str(gymid)]["longitude"]
                if data[str(gymid)]["description"]:
                    description = data[str(gymid)]["description"].replace("\\", r"\\").replace('"', '').replace("\n", "")

            raidJson = ({'id': gymid, 'lat': lat, 'lon': lon, 'hashvalue': hashvalue, 'filename': file, 'name': name, 'description': description, 'gymimage': gymImage, 'count': count, 'creation': creationdate, 'modify': modify,  'level': lvl, 'mon': mon, 'type': type, 'eggPic': eggPic, 'monPic': monPic, 'monname': monName })
            raids.append(raidJson)
        else:
            log.debug("File: " + str(file) + " not found in Database")
            os.remove(str(file))
            continue

    return jsonify(raids)


@app.route("/get_mons")
def get_mons():
    mons = []
    monList =[]

    with open('pokemon.json') as f:
        mondata = json.load(f)

    with open('raidmons.json') as f:
        raidmon = json.load(f)

    for mons in raidmon:
        for mon in mons['DexID']:
            lvl = mons['Level']
            if str(mon).find("_") > -1:
                mon_split = str(mon).split("_")
                mon = mon_split[0]
                frmadd = mon_split[1]
            else:
                frmadd = "00"

            mon = '{:03d}'.format(int(mon))

            monPic = '/asset/pokemon_icons/pokemon_icon_' + mon + '_00.png'
            monName = 'unknown'
            monid = int(mon)

            if str(monid) in mondata:
                monName = mondata[str(monid)]["name"]

            monJson = ({'filename': monPic, 'mon': monid, 'name': monName, 'lvl': lvl})
            monList.append(monJson)

    return jsonify(monList)


@app.route("/get_screens")
def get_screens():
    screens = []

    for file in glob.glob(str(args.raidscreen_path) + "/raidscreen_*.png"):
        creationdate = datetime.datetime.fromtimestamp(creation_date(file)).strftime('%Y-%m-%d %H:%M:%S')

        if args.madmin_time == "12":
            creationdate = datetime.datetime.strptime(creationdate, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %I:%M:%S %p')

        screenJson = ({'filename': file, 'creation': creationdate})
        screens.append(screenJson)

    return jsonify(screens)


@app.route("/get_unknows")
def get_unknows():
    unk = []
    for file in glob.glob("www_hash/unkgym_*.jpg"):
        unkfile = re.search('unkgym_(-?\d+\.?\d+)_(-?\d+\.?\d+)_((?s).*)\.jpg', file)
        creationdate = datetime.datetime.fromtimestamp(creation_date(file)).strftime('%Y-%m-%d %H:%M:%S')
        lat = (unkfile.group(1))
        lon = (unkfile.group(2))
        hashvalue = (unkfile.group(3))

        if args.madmin_time == "12":
            creationdate = datetime.datetime.strptime(creationdate, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %I:%M:%S %p')

        hashJson = ({'lat': lat, 'lon': lon, 'hashvalue': hashvalue, 'filename': file, 'creation': creationdate})
        unk.append(hashJson)

    return jsonify(unk)


@app.route("/get_position")
def get_position():
    position = []
    positionexport = {}
    fileName = args.position_file+'.position'

    for filename in glob.glob('*.position'):
        name = filename.split('.')
        with open(filename, 'r') as f:
            latlon = f.read().strip().split(', ')
            position.append([
                getCoordFloat(latlon[0]),
                getCoordFloat(latlon[1])
            ])
            positionexport[str(name[0])] = position

    return jsonify(positionexport)

    if not os.path.isfile(fileName):
        return jsonify([0, 0])

    with open(fileName) as f:
        latlon = f.read().strip().split(', ')
        if len(latlon) == 2:
            return jsonify([getCoordFloat(latlon[0]), getCoordFloat(latlon[1])])
        else:
            return jsonify([0, 0])


@cache.cached()
@app.route("/get_route")
def get_route():
    route = []
    routeexport = {}

    for filename in glob.glob('*.calc'):
        name = filename.split('.')
        with open(filename, 'r') as f:
            for line in f.readlines():
                latlon = line.strip().split(', ')
                route.append([
                    getCoordFloat(latlon[0]),
                    getCoordFloat(latlon[1])
                ])
            routeexport[str(name[0])] = route
            route = []

    return jsonify(routeexport)


@app.route("/get_spawns")
def get_spawns():
    coords = []
    data = json.loads(db_wrapper.download_spawns())

    for spawnid in data:
        spawn = data[str(spawnid)]
        coords.append({
            'endtime': spawn['endtime'],
            'lat': spawn['lat'],
            'lon': spawn['lon'],
            'spawndef': spawn['spawndef'],
            'lastscan': spawn['lastscan']
            })

    return jsonify(coords)


@cache.cached()
@app.route("/get_gymcoords")
def get_gymcoords():
    coords = []

    data = db_wrapper.get_gym_infos()

    for gymid in data:
        gym = data[str(gymid)]
        coords.append({
            'id': gymid,
            'name': gym['name'],
            'img': gym['url'],
            'lat': gym['latitude'],
            'lon': gym['longitude'],
            'team_id': gym['team_id']
            })

    return jsonify(coords)


@app.route('/gym_img/<path:path>', methods=['GET'])
def pushGyms(path):
    return send_from_directory('ocr/gym_img', path)


@app.route('/www_hash/<path:path>', methods=['GET'])
def pushHashes(path):
    return send_from_directory('ocr/www_hash', path)


@app.route('/screenshots/<path:path>', methods=['GET'])
def pushScreens(path):
    return send_from_directory(args.raidscreen_path, path)


@app.route('/match_unknows', methods=['GET'])
def match_unknows():
    hash = request.args.get('hash')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    return render_template('match_unknown.html', hash=hash, lat=lat, lon=lon, responsive=str(args.madmin_noresponsive).lower())


@app.route('/modify_raid', methods=['GET'])
def modify_raid():
    hash = request.args.get('hash')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lvl = request.args.get('lvl')
    mon = request.args.get('mon')
    return render_template('change_raid.html', hash = hash, lat = lat, lon = lon, lvl = lvl, mon = mon, responsive = str(args.madmin_noresponsive).lower())


@app.route('/modify_gym', methods=['GET'])
def modify_gym():
    hash = request.args.get('hash')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    return render_template('change_gym.html', hash = hash, lat = lat, lon = lon, responsive = str(args.madmin_noresponsive).lower())


@app.route('/modify_mon', methods=['GET'])
def modify_mon():
    hash = request.args.get('hash')
    gym = request.args.get('gym')
    lvl = request.args.get('lvl')
    return render_template('change_mon.html', hash = hash, gym = gym, lvl = lvl, responsive = str(args.madmin_noresponsive).lower())


@app.route('/asset/<path:path>', methods=['GET'])
def pushAssets(path):
    return send_from_directory(args.pogoasset, path)


@app.route('/config')
def config():
    fieldwebsite = []
    oldvalues = []
    sel = ''

    edit = False
    edit = request.args.get('edit')
    type = request.args.get('type')
    block = request.args.get('block')
    area = request.args.get('area')
    fieldwebsite.append('<form action=/addedit id=settings>')
    fieldwebsite.append('<input type=hidden name=block value=' + block + '>')
    fieldwebsite.append('<input type=hidden name=mode value=' + type + '>')
    fieldwebsite.append('<input type=hidden name=area value=' + area + '>')
    if edit:
        fieldwebsite.append('<input type=hidden name=edit value=' + edit + '>')
        with open('configs/mappings.json') as f:
            mapping = json.load(f)
            for oldfields in mapping[area]:
                if 'name' in oldfields:
                    if oldfields['name'] == edit:
                        oldvalues = oldfields
                        _checkfield = 'name'
                if 'origin' in oldfields:
                    if oldfields['origin'] == edit:
                        oldvalues = oldfields
                        _checkfield = 'origin'
                if 'username' in oldfields:
                    if oldfields['username'] == edit:
                        oldvalues = oldfields
                        _checkfield = 'username'

    with open('madmin/static/vars/vars_parser.json') as f:
        vars = json.load(f)

    for area in vars[area]:
        if 'name' in area:
            if area['name'] == type:
                _name = area['name']
                compfields = area
        if 'origin' in area:
            if area['origin'] == type:
                _name = area['origin']
                compfields = area
        if 'username' in area:
            if area['username'] == type:
                _name = area['username']
                compfields = area

    for field in compfields[block]:
            req = ''
            lock = field['settings'].get("lockonedit", False)
            lockvalue = ''
            if lock:
                lockvalue = 'readonly'
            if field['settings']['type'] == 'text':
                req = field['settings'].get('require', 'false')
                if req in ('true'):
                    req = "required"
                if edit:
                    if block == "settings":
                        if field['name'] in oldvalues['settings']:
                            if str(oldvalues['settings'][field['name']]) != str('None'):
                                val = str(oldvalues['settings'][field['name']])
                            else:
                                val = ''
                        else:
                            val = ''
                    else:
                        if field['name'] in oldvalues:
                            if str(oldvalues[field['name']]) != str('None'):
                                val = str(oldvalues[field['name']])
                            else:
                                val = ''
                        else:
                            val = ''
                    fieldwebsite.append('<b>' + str(field['name']) + '</b><br>' + str(field['settings']['description']) + ' <br><input type=text name=' + str(field['name']) + ' value="' + val + '" ' + lockvalue + ' ' + req + '>')
                else:
                    fieldwebsite.append('<b>' + str(field['name']) + '</b><br>' + str(field['settings']['description']) + ' <br><input type=text name=' + str(field['name']) + ' ' + req + '>')
            if field['settings']['type'] == 'option':
                req = field['settings'].get('require', 'false')
                if req in ('true'):
                    req = "required"
                _temp = '<b>' + str(field['name']) + '</b><br>' + str(field['settings']['description']) + ' <br><select name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
                _options = field['settings']['values'].split('|')
                for option in _options:
                    if edit:
                        if block == "settings":
                            if option in oldvalues['settings']:
                                if str(oldvalues[field['settings']['name']]).lower() == str(option).lower():
                                    sel = 'selected'
                        else:
                            if str(oldvalues[field['name']]).lower() == str(option).lower():
                                sel = 'selected'
                    _temp = _temp + '<option value=' + str(option) + ' ' + sel + '>' + str(option) + '</option>'
                    sel = ''
                _temp = _temp + '</select>'
                fieldwebsite.append(str(_temp))
            if field['settings']['type'] == 'areaselect':
                req = field['settings'].get('require', 'false')
                if req in ('true'):
                    req = "required"
                _temp = '<b>' + str(field['name']) + '</b><br>' + str(field['settings']['description']) + ' <br><select name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
                with open('configs/mappings.json') as f:
                    mapping = json.load(f)
                mapping['areas'].append({'name': None})

                for option in mapping['areas']:
                    if edit:
                        if block == "settings":
                            if str(oldvalues[field['settings']['name']]).lower() == str(option['name']).lower():
                                sel = 'selected'
                            else:
                                if oldvalues[field['settings']['name']] == '':
                                    sel = 'selected'
                        else:
                            if field['name'] in oldvalues:
                                if str(oldvalues[field['name']]).lower() == str(option['name']).lower():
                                    sel = 'selected'
                            else:
                                if not option['name']:
                                    sel = 'selected'
                    _temp = _temp + '<option value="' + str(option['name']) + '" ' + sel + '>' + str(option['name']) + '</option>'
                    sel = ''
                _temp = _temp + '</select>'
                fieldwebsite.append(str(_temp))

    if edit:
        header = "Edit " + edit + " (" + type + ")"
    else:
        header = "Add new " + type

    fieldwebsite.append('<input type=submit value="Save"></form> ')

    return render_template('parser.html', editform=fieldwebsite, header=header)


@app.route('/delsetting', methods=['GET', 'POST'])
def delsetting():

    edit = request.args.get('edit')
    type = request.args.get('type')
    block = request.args.get('block')
    area = request.args.get('area')

    with open('configs/mappings.json') as f:
        mapping = json.load(f)

    i = 0
    for asd in mapping[area]:
        if 'name' in mapping[area][i]:
                _checkfield = 'name'
        if 'origin' in mapping[area][i]:
                _checkfield = 'origin'
        if 'username' in mapping[area][i]:
                _checkfield = 'username'

        if str(edit) in str(mapping[area][i][_checkfield]):
            del mapping[area][i]

        i += 1

    with open('configs/mappings.json', 'w') as outfile:
        json.dump(mapping, outfile, indent=4, sort_keys=True)

    return redirect("/showsettings", code=302)


@app.route('/addedit', methods=['GET', 'POST'])
def addedit():
    data = request.args
    datavalue = {}

    for ase, key in data.items():
        datavalue[ase] = key

    edit = datavalue.get("edit", False)
    block = datavalue.get("block", False)
    type = datavalue.get("type", False)
    name = datavalue.get("name", False)
    area = datavalue.get("area", False)
    delete = datavalue.get("del", False)

    with open('configs/mappings.json') as f:
        mapping = json.load(f)

    with open('madmin/static/vars/settings.json') as f:
        settings = json.load(f)

    if edit:
        i = 0
        for asd in mapping[area]:
            if 'name' in mapping[area][i]:
                    _checkfield = 'name'
            if 'origin' in mapping[area][i]:
                    _checkfield = 'origin'
            if 'username' in mapping[area][i]:
                    _checkfield = 'username'

            if str(edit) in str(mapping[area][i][_checkfield]):
                if str(block) == str("settings"):
                    for ase, key in data.items():
                        if key == '':
                            if ase in mapping[area][i]['settings']:
                                del mapping[area][i]['settings'][ase]
                        elif key in area:
                            continue
                        else:
                            if key == 'true':
                                key = bool(True)
                            elif key == 'false':
                                key = bool(False)
                            elif key.isdigit():
                                key = int(key)
                            elif key == "None":
                                key = None
                            if str(ase) not in ('block', 'area', 'type', 'edit'):
                                mapping[area][i]['settings'][ase] = key

                else:
                    for ase, key in data.items():
                        if ase in mapping[area][i]:
                            if key == '':
                                if ase in mapping[area][i]:
                                    del mapping[area][i][ase]
                            elif key in area:
                                continue
                            else:
                                if key in 'true':
                                    key = bool(True)
                                elif key in 'false':
                                    key = bool(False)
                                elif key.isdigit():
                                    key = int(key)
                                elif key == "None":
                                    key = None
                                if str(ase) not in ('block', 'area', 'type', 'edit'):
                                    mapping[area][i][ase] = key
                        else:
                            if key in area:
                                continue
                            else:
                                if key == 'true':
                                    key = bool(True)
                                elif key == 'false':
                                    key = bool(False)
                                elif key.isdigit():
                                    key = int(key)
                                elif key == "None":
                                    key = None
                                if str(ase) not in ('block', 'area', 'type', 'edit'):
                                    new = {}
                                    new[ase] = key
                                    mapping[area][i][ase] = key
            i += 1
    else:
        new = {}
        for ase, key in data.items():
            if key != '' and key not in area:
                if key == 'true':
                    key = bool(True)
                elif key == 'false':
                    key = bool(False)
                elif key.isdigit():
                    key = int(key)
                elif key == "None":
                    key = None
                if str(ase) not in ('block', 'area', 'type', 'edit'):
                    new[ase] = key

        if str(block) == str("settings"):
            mapping[area]['settings'].append(new)
        else:
            if (settings[area]['has_settings']) in ('true'):
                new['settings'] = {}
            mapping[area].append(new)

    with open('configs/mappings.json', 'w') as outfile:
        json.dump(mapping, outfile, indent=4, sort_keys=True)

    return redirect("/showsettings", code=302)


@app.route('/showsettings', methods=['GET', 'POST'])
def showsettings():
    table=''
    with open('configs/mappings.json') as f:
        mapping = json.load(f)
    with open('madmin/static/vars/settings.json') as f:
        settings = json.load(f)
    with open('madmin/static/vars/vars_parser.json') as f:
        vars = json.load(f)

    for var in vars:
        line, quickadd, quickline = '', '', ''
        header = '<thead><tr><th><b>' + (var.upper()) + '</b> <a href=/addnew?area=' + var + '>[Add new]</a></th><th>Basedata</th><th>Settings</th><th>Delete</th></tr></thead>'
        subheader = '<tr><td colspan="4">' + settings[var]['description'] + '</td></tr>'
        edit = '<td></td>'
        editsettings = '<td></td>'
        _typearea = var
        _field = settings[var]['field']
        _quick = settings[var].get('quickview', False)
        _quicksett = settings[var].get('quickview_settings', False)

        for output in mapping[var]:
            quickadd, quickline = '', ''
            mode = output.get('mode', _typearea)
            if settings[var]['could_edit']:
                edit = '<td><a href=/config?type=' + str(mode) + '&area=' + str(_typearea) + '&block=fields&edit=' + str(output[_field]) + '>[Edit]</a></td>'
            else:
                edit = '<td></td>'
            if settings[var]['has_settings'] in ('true'):
                editsettings = '<td><a href=/config?type=' + str(mode) + '&area=' + str(_typearea) + '&block=settings&edit=' + str(output[_field]) + '>[Edit Settings]</a></td>'
            else:
                editsettings = '<td></td>'
            delete = '<td><a href=/delsetting?type=' + str(mode) + '&area=' + str(_typearea) + '&block=settings&edit=' + str(output[_field]) + '&del=true>[Delete]</a></td>'

            line = line + '<tr><td><b>' + str(output[_field]) + '</b></td>' + str(edit) + str(editsettings) + str(delete) + '</tr>'
            
            if _quick:
                for quickfield in _quick.split('|'):
                    if output.get(quickfield, False):
                        quickadd = quickadd + str(quickfield) + ': ' + str(output.get(quickfield, '')) + '<br>'
                quickline = quickline + '<tr><td></td><td class=quick>' + str(quickadd) + '</td>'
            quickadd = ''
            if _quicksett:
                for quickfield in _quicksett.split('|'):
                    if output['settings'].get(quickfield, False):
                        quickadd = quickadd + str(quickfield) + ': ' + str(output['settings'].get(quickfield, '')) + '<br>'
                quickline = quickline + '<td colspan="2" class=quick>' + str(quickadd) + '</td></tr>'

                
            line = line + quickline

            
        table = table + header + subheader + line

    return render_template('settings.html', settings='<table>' + table + '</table>')

    return jsonify(table)


@app.route('/addnew', methods=['GET', 'POST'])
def addnew():
    area = request.args.get('area')
    line = ''
    with open('madmin/static/vars/vars_parser.json') as f:
        settings = json.load(f)
    if (len(settings[area])) == 1:
        return redirect('config?type=' + area + '&area=' + area + '&block=fields')

    for output in settings[area]:
        line = line + '<h3><a href=config?type=' + str(output['name']) + '&area=' + str(area) + '&block=fields>'+str(output['name'])+'</a></h3><h5>'+str(output['description'])+'</h5><hr>'

    return render_template('sel_type.html', line=line)


def decodeHashJson(hashJson):
    data = json.loads(hashJson)
    raidGym = data['gym']
    raidLvl = data["lvl"]
    raidMon = data["mon"]

    return raidGym, raidLvl, raidMon


def encodeHashJson(gym, lvl, mon):
    hashJson = json.dumps({'gym': gym, 'lvl': lvl, 'mon': mon}, separators=(',', ':'))
    return hashJson


def getAllHash(type):
    rv = db_wrapper.get_all_hash(type)
    hashRes = {}
    for result in rv:
        hashRes[result[1]] = ({'id': str(result[0]), 'type': result[2], 'count': result[3], 'modify': str(result[4])})
    # data_json = json.dumps(hashRes, sort_keys=True, indent=4, separators=(',', ': '))
    data_json = hashRes
    return json.dumps(hashRes, indent=4, sort_keys=True)


def getCoordFloat(coordinate):
    return floor(float(coordinate) * (10 ** 5)) / float(10 ** 5)


def creation_date(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See http://stackoverflow.com/a/39501288/1709587 for explanation.
    """
    if platform.system() == 'Windows':
        return os.path.getctime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime


if __name__ == "__main__":
    app.run()
    # host='0.0.0.0', port=int(args.madmin_port), threaded=False)

