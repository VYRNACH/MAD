import json
import time
from datetime import datetime, timedelta
import logging
import mysql
from threading import Lock, Semaphore

from bitstring import BitArray
from mysql.connector.pooling import MySQLConnectionPool
from abc import ABC, abstractmethod
import numpy as np

from utils.s2Helper import S2Helper

log = logging.getLogger(__name__)


class DbWrapperBase(ABC):
    def_spawn = 240

    def __init__(self, args, webhook_helper):
        self.application_args = args
        self.host = args.dbip
        self.port = args.dbport
        self.user = args.dbusername
        self.password = args.dbpassword
        self.database = args.dbname
        self.timezone = args.timezone
        self.pool = None
        self.pool_mutex = Lock()
        self._init_pool()
        self.connection_semaphore = Semaphore(self.application_args.db_poolsize)
        self.webhook_helper = webhook_helper

    def _init_pool(self):
        log.info("Connecting pool to DB")
        self.pool_mutex.acquire()
        dbconfig = {"database": self.database, "user": self.user, "host": self.host, "password": self.password,
                    "port": self.port}
        self.pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="db_wrapper_pool",
                                                                pool_size=self.application_args.db_poolsize,
                                                                **dbconfig)
        self.pool_mutex.release()

    def close(self, conn, cursor):
        """
        A method used to close connection of mysql.
        :param conn:
        :param cursor:
        :return:
        """
        cursor.close()
        conn.close()

    def execute(self, sql, args=None, commit=False):
        """
        Execute a sql, it could be with args and with out args. The usage is
        similar with execute() function in module pymysql.
        :param sql: sql clause
        :param args: args need by sql clause
        :param commit: whether to commit
        :return: if commit, return None, else, return result
        """
        # get connection form connection pool instead of create one.
        self.connection_semaphore.acquire()
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        if args:
            cursor.execute(sql, args)
        else:
            cursor.execute(sql)
        if commit is True:
            affected_rows = cursor.rowcount
            conn.commit()
            self.close(conn, cursor)
            self.connection_semaphore.release()
            return affected_rows
        else:
            res = cursor.fetchall()
            self.close(conn, cursor)
            self.connection_semaphore.release()
            return res

    def executemany(self, sql, args, commit=False):
        """
        Execute with many args. Similar with executemany() function in pymysql.
        args should be a sequence.
        :param sql: sql clause
        :param args: args
        :param commit: commit or not.
        :return: if commit, return None, else, return result
        """
        # get connection form connection pool instead of create one.
        self.connection_semaphore.acquire()
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        cursor.executemany(sql, args)

        if commit is True:
            conn.commit()
            self.close(conn, cursor)
            self.connection_semaphore.release()
            return None
        else:
            res = cursor.fetchall()
            self.close(conn, cursor)
            self.connection_semaphore.release()
            return res

    @abstractmethod
    def ensure_last_updated_column(self):
        """
        We add a last_updated column to monocle
        """
        pass

    @abstractmethod
    def auto_hatch_eggs(self):
        """
        Check the entire DB for unhatched level 5 eggs and updates the mon ID if there is only one
        possible raidmon
        """
        pass

    @abstractmethod
    def db_timestring_to_unix_timestamp(self, timestring):
        """
        Converts a DB timestring to a unix timestamp (seconds since epoch)
        """
        pass

    @abstractmethod
    def get_next_raid_hatches(self, delay_after_hatch, geofence_helper=None):
        """
        In order to build a priority queue, we need to be able to check for the next hatches of raid eggs
        The result may not be sorted by priority, to be done at a higher level!
        :return: unsorted list of next hatches within delay_after_hatch
        """
        pass

    @abstractmethod
    def submit_raid(self, gym, pkm, lvl, start, end, type, raid_no, capture_time,
                    unique_hash="123", mon_with_no_egg=False):
        """
        Insert or update raid in DB and send webhook
        :return: if raid has all the required values = True, else False
        """
        pass

    @abstractmethod
    def read_raid_endtime(self, gym, raid_no, unique_hash="123"):
        """
        Check if a raid already has an endtime and return True/False appropriately
        :return: if raid has endtime = True, else False
        """
        pass

    @abstractmethod
    def get_raid_endtime(self, gym, raid_no, unique_hash="123"):
        """
        Retrieves the time the requested raid ends - if present
        :return: returns (Boolean, Value) with Value being the time or None, Boolean being True/False appropriately
        """
        pass

    @abstractmethod
    def raid_exist(self, gym, type, raid_no, unique_hash="123", mon=0):
        """
        Checks if a raid is already present in the DB
        :return: returns True/False indicating if a raid is already present in the database
        """
        pass

    @abstractmethod
    def refresh_times(self, gym, raid_no, capture_time, unique_hash="123"):
        """
        Update last_modified/last_scanned/updated of a gym
        """
        pass

    @abstractmethod
    def get_near_gyms(self, lat, lng, hash, raid_no, dist, unique_hash="123"):
        """
        Retrieve gyms around a given lat, lng within the given dist
        :return: returns list of gyms within dist sorted by distance
        """
        pass

    @abstractmethod
    def set_scanned_location(self, lat, lng, capture_time):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        pass

    @abstractmethod
    def get_gym_infos(self, id=False):
        """
        Retrieve all the gyminfos from DB
        :return: returns dict containing all the gyminfos contained in the DB
        """
        pass

    @abstractmethod
    def gyms_from_db(self, geofence_helper):
        """
        Retrieve all the gyms valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        pass

    @abstractmethod
    def stops_from_db(self, geofence_helper):
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        pass

    @abstractmethod
    def update_insert_weather(self, cell_id, gameplay_weather, capture_time,
                               cloud_level=0, rain_level=0, wind_level=0,
                               snow_level=0, fog_level=0, wind_direction=0,
                               weather_daytime=0):
        """
        Updates the weather in a given cell_id
        """
        pass

    @abstractmethod
    def submit_mon_iv(self, id, type, lat, lon, desptime, spawnid, gender, weather, costume, form,
                      cp, move_1, move_2, weight, height, individual_attack, individual_defense,
                      individual_stamina, cpmulti):
        """
        Update/Insert a mon with IVs
        """
        pass

    @abstractmethod
    def submit_mons_map_proto(self, map_proto):
        """
        Update/Insert mons from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_pokestops_map_proto(self, map_proto):
        """
        Update/Insert pokestops from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_gyms_map_proto(self, map_proto):
        """
        Update/Insert gyms from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_raids_map_proto(self, map_proto):
        """
        Update/Insert raids from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_weather_map_proto(self, map_proto, received_timestamp):
        """
        Update/Insert weather from a map_proto dict
        """
        pass

    @abstractmethod
    def download_gym_images(self):
        pass

    def download_gym_infos(self):
        """
        Download gym images (populated in DB) and store the images in /ocr/gym_img/
        """
        log.debug("{DbWrapperBase::download_gym_infos} called")
        import json
        import io

        gym_infos = self.get_gym_infos()

        with io.open('gym_info.json', 'w') as outfile:
            outfile.write(str(json.dumps(gym_infos, indent=4, sort_keys=True)))

    def create_hash_database_if_not_exists(self):
        """
        In order to store 'hashes' of crops/images, we require a table to store those hashes
        """
        log.debug("{DbWrapperBase::create_hash_database_if_not_exists} called")
        log.debug('Creating hash db in database')

        query = (' Create table if not exists trshash ( ' +
                 ' hashid MEDIUMINT NOT NULL AUTO_INCREMENT, ' +
                 ' hash VARCHAR(255) NOT NULL, ' +
                 ' type VARCHAR(10) NOT NULL, ' +
                 ' id VARCHAR(255) NOT NULL, ' +
                 ' count INT(10) NOT NULL DEFAULT 1, ' +
                 ' modify DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, ' +
                 ' PRIMARY KEY (hashid))')
        log.debug(query)
        self.execute(query, commit=True)

        return True

    def check_for_hash(self, imghash, type, raid_no, distance, unique_hash="123"):
        log.debug("{DbWrapperBase::check_for_hash} called")
        log.debug("[Crop: %s (%s) ] check_for_hash: Checking for hash in db" % (str(raid_no), str(unique_hash)))

        query = (
            "SELECT id, hash, "
            "BIT_COUNT( "
            "CONVERT((CONV(hash, 16, 10)), UNSIGNED) "
            "^ "
            "CONVERT((CONV(%s, 16, 10)), UNSIGNED)) as hamming_distance, type, count, modify "
            "FROM trshash "
            "HAVING hamming_distance < %s AND type = %s "
            "ORDER BY hamming_distance ASC"
        )
        vals = (str(imghash), distance, str(type))

        res = self.execute(query, vals)
        number_of_rows = len(res)

        log.debug("[Crop: %s (%s) ] check_for_hash: Found hashes in database: %s" %
                  (str(raid_no), str(unique_hash), str(number_of_rows)))

        if number_of_rows > 0:
            log.debug("[Crop: %s (%s) ] check_for_hash: returning found ID" % (str(raid_no), str(unique_hash)))
            for row in res:
                log.debug("[Crop: %s (%s) ] check_for_hash: ID = %s"
                          % (str(raid_no), str(unique_hash), str(row[0])))
                log.debug("{DbWrapperBase::check_for_hash} done")
                return True, row[0], row[1], row[4], row[5]
        else:
            log.debug("[Crop: %s (%s) ] check_for_hash: No matching hash found" % (str(raid_no), str(unique_hash)))
            log.debug("{DbWrapperBase::check_for_hash} done")
            return False, None, None, None, None

    def get_all_hash(self, type):
        log.debug("{DbWrapperBase::get_all_hash} called")
        query = (
            "SELECT id, hash, type, count, modify "
            "FROM trshash "
            "HAVING type = %s"
        )
        vals = (str(type),)
        log.debug(query)

        res = self.execute(query, vals)

        return res

    def insert_hash(self, imghash, type, id, raid_no, unique_hash="123"):
        log.debug("{DbWrapperBase::insert_hash} called")
        if type == 'raid':
            distance = 4
        else:
            distance = 4

        double_check = self.check_for_hash(imghash, type, raid_no, distance)

        if double_check[0]:
            log.debug("[Crop: %s (%s) ] insert_hash: Already in DB, updating counter"
                      % (str(raid_no), str(unique_hash)))

        # TODO: consider INSERT... ON DUPLICATE KEY UPDATE ??

        if not double_check[0]:
            query = (
                "INSERT INTO trshash (hash, type, id) "
                "VALUES (%s, %s, %s)"
            )
            vals = (str(imghash), str(type), id)
        else:
            query = (
                "UPDATE trshash "
                "SET count=count+1, modify=NOW() "
                "WHERE hash=%s"
            )
            vals = (str(imghash),)

        self.execute(query, vals, commit=True)
        log.debug("{DbWrapperBase::insert_hash} done")
        return True

    def delete_hash_table(self, ids, type, mode=' not in ', field=' id '):
        log.debug("{DbWrapperBase::delete_hash_table} called")
        log.debug('Deleting old Hashes of type %s' % type)
        log.debug('Valid ids: %s' % ids)

        query = (
                "DELETE FROM trshash "
                "WHERE " + field + " " + mode + " (%s) "
                                                "AND type like %s"
        )
        vals = (str(ids), str(type),)
        log.debug(query)

        self.execute(query, vals, commit=True)
        return True

    def clear_hash_gyms(self, mons):
        log.debug("{DbWrapperBase::clear_hash_gyms} called")
        data = []
        query = (
            "SELECT hashid "
            "FROM trshash "
            "WHERE id LIKE '%\"mon\":\"%s\"%' AND type='raid'"
        )

        mon_split = mons.split('|')
        for mon in mon_split:
            args = (int(mon),)
            res = self.execute(query, args)
            for dbid in res:
                data.append(int(dbid[0]))

        _mon_list = ','.join(map(str, data))
        log.debug('clearHashGyms: Read Raid Hashes with known Mons')
        if len(data) > 0:
            query = ('DELETE FROM trshash ' +
                     ' WHERE hashid NOT IN (' + _mon_list + ')' +
                     ' AND type=\'raid\'')
            self.execute(query, commit=True)
        log.info('clearHashGyms: Deleted Raidhashes with unknown mons')

    def getspawndef(self, spawn_id):
        log.debug("{DbWrapperBase::getspawndef} called")
        query = (
            "SELECT spawndef "
            "FROM trs_spawn "
            "WHERE spawnpoint=%s"
        )
        vals = (spawn_id,)

        res = self.execute(query, vals)
        ret = [row[0] for row in res]
        return ret

    def submit_spawnpoints_map_proto(self, map_proto):
        log.debug("{DbWrapperBase::submit_spawnpoints_map_proto} called")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        spawnpoint_args, spawnpoint_args_unseen = [], []

        query_spawnpoints = (
            "INSERT INTO trs_spawn (spawnpoint, latitude, longitude, earliest_unseen, "
            "last_scanned, spawndef, calc_endminsec) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_scanned=VALUES(last_scanned), "
            "earliest_unseen=LEAST(earliest_unseen, VALUES(earliest_unseen)), "
            "spawndef=VALUES(spawndef), calc_endminsec=VALUES(calc_endminsec)"
            ""
        )

        query_spawnpoints_unseen = (
            "INSERT INTO trs_spawn (spawnpoint, latitude, longitude, earliest_unseen, last_non_scanned, spawndef) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE spawndef=VALUES(spawndef), last_non_scanned=VALUES(last_non_scanned)"
            ""
        )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dt = datetime.now()

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon['spawnpoint_id']), 16)
                lat, lng, alt = S2Helper.get_position_from_cell(int(str(wild_mon['spawnpoint_id']) + '00000', 16))
                despawntime = wild_mon['time_till_hidden']

                minpos = self._get_min_pos_in_array()
                # TODO: retrieve the spawndefs by a single executemany and pass that...

                spawndef = self.getspawndef(spawnid)
                spawndef_ = False
                for t in spawndef:
                    spawndef_ = t

                if spawndef_:
                    newspawndef = self._set_spawn_see_minutesgroup(spawndef_, minpos)
                else:
                    newspawndef = self._set_spawn_see_minutesgroup(DbWrapperBase.def_spawn, minpos)

                last_scanned = None
                last_non_scanned = None

                if 0 <= int(despawntime) <= 90000:
                    fulldate = dt + timedelta(milliseconds=despawntime)
                    earliest_unseen = int(despawntime)
                    last_scanned = now
                    calcendtime = fulldate.strftime("%M:%S")

                    spawnpoint_args.append(
                        (
                            spawnid, lat, lng, earliest_unseen, last_scanned, newspawndef, calcendtime
                        )
                    )

                else:
                    earliest_unseen = 99999999
                    last_non_scanned = now
                    calcendtime = None

                    spawnpoint_args_unseen.append(
                        (
                            spawnid, lat, lng, earliest_unseen, last_non_scanned, newspawndef
                        )
                    )

        self.executemany(query_spawnpoints, spawnpoint_args, commit=True)
        self.executemany(query_spawnpoints_unseen, spawnpoint_args_unseen, commit=True)

    def submitspsightings(self, spid, encid, secs):
        log.debug("{DbWrapperBase::submitspsightings} called")
        if 0 <= int(secs) <= 90000:
            query = (
                "INSERT INTO trs_spawnsightings (encounter_id, spawnpoint_id, tth_secs) "
                "VALUES (%s, %s, %s)"
            )
            vals = (
                encid, spid, secs
            )
        else:
            query = (
                "INSERT INTO trs_spawnsightings (encounter_id, spawnpoint_id) "
                "VALUES (%s, %s)"
            )
            vals = (
                encid, spid
            )

        self.execute(query, vals, commit=True)

    def get_spawn_infos(self):
        log.debug("{DbWrapperBase::get_spawn_infos} called")
        query = (
            "SELECT count(spawnpoint), "
            "ROUND ( "
            "(COUNT(calc_endminsec) + 1) / (COUNT(*) + 1) * 100, 2) AS percent "
            "FROM trs_spawn"
        )

        found = self.execute(query)
        log.info("Spawnpoint statistics: %s, Spawnpoints with detected endtime: %s"
                 % (str(found[0][0]), str(found[0][1])))

        return float(found[0][1])

    def get_detected_spawns(self, geofence_helper):
        log.debug("{DbWrapperBase::get_detected_spawns} called")

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn"
        )
        list_of_coords = []
        res = self.execute(query)
        for (latitude, longitude) in res:
            list_of_coords.append([latitude, longitude])

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
            log.debug(geofenced_coords)
            return geofenced_coords
        else:
            to_return = np.zeros(shape=(len(list_of_coords), 2))
            for i in range(len(to_return)):
                to_return[i][0] = list_of_coords[i][0]
                to_return[i][1] = list_of_coords[i][1]
            return to_return

    def get_undetected_spawns(self, geofence_helper):
        log.debug("{DbWrapperBase::get_undetected_spawns} called")

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE calc_endminsec is NULL"
        )
        list_of_coords = []
        res = self.execute(query)
        for (latitude, longitude) in res:
            list_of_coords.append([latitude, longitude])

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
            log.debug(geofenced_coords)
            return geofenced_coords
        else:
            import numpy as np
            to_return = np.zeros(shape=(len(list_of_coords), 2))
            for i in range(len(to_return)):
                to_return[i][0] = list_of_coords[i][0]
                to_return[i][1] = list_of_coords[i][1]
            return to_return

    def get_detected_endtime(self, spawn_id):
        log.debug("{DbWrapperBase::get_detected_endtime} called")

        query = (
            "SELECT calc_endminsec "
            "FROM trs_spawn "
            "WHERE spawnpoint=%s"
        )
        args = (
            spawn_id,
        )

        found = self.execute(query, args)

        if found[0][0]:
            return str(found[0][0])
        else:
            return False

    def _gen_endtime(self, known_despawn):
        hrmi = known_despawn.split(':')
        known_despawn = datetime.now().replace(hour=0, minute=int(hrmi[0]), second=int(hrmi[1]), microsecond=0)
        now = datetime.now()
        if now.minute <= known_despawn.minute:
            despawn = now + timedelta(minutes=known_despawn.minute - now.minute,
                                      seconds=known_despawn.second - now.second)
        elif now.minute > known_despawn.minute:
            despawn = now + timedelta(hours=1) - timedelta(
                minutes=(now.minute - known_despawn.minute), seconds=now.second - known_despawn.second)
        else:
            return None
        return time.mktime(despawn.timetuple())

    def _get_min_pos_in_array(self):
        min = datetime.now().strftime("%M")

        if int(min) >= 0:
            pos = 4
        elif int(min) >= 15:
            pos = 5
        elif int(min) >= 30:
            pos = 6
        elif int(min) >= 45:
            pos = 7
        else:
            pos = None

        return pos

    def _set_spawn_see_minutesgroup(self, spawndef, pos):
        # b = BitArray([int(digit) for digit in bin(spawndef)[2:]])
        b = BitArray(uint=spawndef, length=8)
        if pos == 4:
            b[0] = 0
            b[4] = 1
        if pos == 5:
            b[1] = 0
            b[5] = 1
        if pos == 6:
            b[2] = 0
            b[6] = 1
        if pos == 7:
            b[3] = 0
            b[7] = 1
        return b.uint

    def check_and_create_spawn_tables(self):
        log.debug("{DbWrapperBase::check_and_create_spawn_tables} called")

        query_trs_spawn = ('CREATE TABLE IF NOT EXISTS `trs_spawn` ('
                           '`spawnpoint` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL, '
                           '`latitude` double NOT NULL, '
                           '`longitude` double NOT NULL, '
                           '`spawndef` int(11) NOT NULL DEFAULT "240", '
                           '`earliest_unseen` int(6) NOT NULL, '
                           '`last_scanned` datetime DEFAULT NULL, '
                           '`first_detection` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, '
                           '`last_non_scanned` datetime DEFAULT NULL, '
                           '`calc_endminsec` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL, '
                           'UNIQUE KEY `spawnpoint_2` (`spawnpoint`), '
                           'KEY `spawnpoint` (`spawnpoint`) '
                           ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;'
                           )

        query_trs_spawnsightings = ('CREATE TABLE IF NOT EXISTS `trs_spawnsightings` ('
                                    '`id` int(11) NOT NULL AUTO_INCREMENT, '
                                    '`encounter_id` bigint(20) UNSIGNED NOT NULL, '
                                    '`spawnpoint_id` bigint(20) UNSIGNED NOT NULL, '
                                    '`scan_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, '
                                    '`tth_secs` int(11) DEFAULT NULL, '
                                    'PRIMARY KEY (`id`), '
                                    'KEY `trs_spawnpointdd_spawnpoint_id` (`spawnpoint_id`) '
                                    ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;'
                                    )

        self.execute(query_trs_spawn, commit=True)
        self.execute(query_trs_spawnsightings, commit=True)

    def download_spawns(self):
        log.debug("dbWrapper::download_spawns")
        spawn = {}

        query = (
            "SELECT spawnpoint, latitude, longitude, calc_endminsec, "
            "spawndef, last_scanned "
            "FROM `trs_spawn`"
        )

        res = self.execute(query)
        for (spawnid, lat, lon, endtime, spawndef, last_scanned) in res:
            spawn[spawnid] = {'lat': lat, 'lon': lon, 'endtime': endtime, 'spawndef': spawndef, 'lastscan': str(last_scanned)}

        return str(json.dumps(spawn, indent=4, sort_keys=True))
