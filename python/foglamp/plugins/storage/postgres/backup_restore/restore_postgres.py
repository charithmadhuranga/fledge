#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2017

""" Restores the entire FogLAMP repository from a previous backup.

It executes a full cold restore,
FogLAMP will be stopped before the start of the restore and restarted at the end.

It could work also without the Configuration Manager
retrieving the parameters for the execution from the local file 'restore_configuration_cache.json'.
The local file is used as a cache of information retrieved from the Configuration Manager.

Usage:
    --backup-id                     Restore a specific backup retrieving the related information from the
                                    Storage Layer.
         --file                     Restore a backup from a specific file, the full path should be provided
                                    like for example : --file=/tmp/foglamp_2017_09_25_15_10_22.dump

    The latest backup will be restored if no options is used.

Execution samples :

restore_postgres --backup-id=29
restore_postgres --file=/tmp/foglamp_backup_2017_12_04_13_57_37.dump
restore_postgres

Exit code :
    0    = OK
    >=1  = Warning/Error

"""

import time
# noinspection PyUnresolvedReferences
import sys
import os
import signal
import asyncio
import uuid

from foglamp.services.core import server
from foglamp.common.process import FoglampProcess
from foglamp.common import logger

import foglamp.plugins.storage.postgres.backup_restore.lib as lib
import foglamp.plugins.storage.postgres.backup_restore.exceptions as exceptions

__author__ = "Stefano Simonelli"
__copyright__ = "Copyright (c) 2017 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_MODULE_NAME = "foglamp_restore_postgres_module"

_MESSAGES_LIST = {

    # Information messages
    "i000001": "Execution started.",
    "i000002": "Execution completed.",

    # Warning / Error messages
    "e000001": "cannot start the logger - error details |{0}|",
    "e000002": "an error occurred during the restore operation - error details |{0}|",
    "e000003": "invalid command line arguments - error details |{0}|",
    "e000004": "cannot complete the initialization - error details |{0}|",
}
""" Messages used for Information, Warning and Error notice """


# Log definitions
_logger = None

_LOG_LEVEL_DEBUG = 10
_LOG_LEVEL_INFO = 20

# FIXME:
# _LOGGER_LEVEL = _LOG_LEVEL_INFO
# _LOGGER_DESTINATION = logger.SYSLOG
_LOGGER_LEVEL = _LOG_LEVEL_DEBUG
# _LOGGER_DESTINATION = logger.CONSOLE
# _LOGGER_DESTINATION = logger.SYSLOG
_LOGGER_DESTINATION = logger.SYSLOG


def _signal_handler(_signo,  _stack_frame):
    """ Handles signals to avoid restore termination doing FogLAMP stop

    Args:
    Returns:
    Raises:
    """

    short_stack_frame = str(_stack_frame)[:100]
    _logger.debug("{func} - signal |{signo}| - info |{ssf}| ".format(
                                                                    func="_signal_handler",
                                                                    signo=_signo,
                                                                    ssf=short_stack_frame))


class Restore(object):
    """ Provides external functionality/integration to Restore a Backup
    """

    _MODULE_NAME = "foglamp_restore_postgres_api"

    _logger = None

    _MESSAGES_LIST = {

        # Information messages
        "i000000": "general information",
        "i000001": "On demand restore successfully launched.",

        # Warning / Error messages
        "e000000": "general error",
        "e000001": "cannot launch on demand restore - error details |{0}|",
    }
    """ Messages used for Information, Warning and Error notice """

    def __init__(self, _storage):
        self._storage = _storage

        if not Restore._logger:
            Restore._logger = logger.setup(
                                            self._MODULE_NAME,
                                            destination=_LOGGER_DESTINATION,
                                            level=_LOGGER_LEVEL)

    async def restore_backup(self, backup_id: int):
        """ Starts an asynchronous restore process to restore the state of FogLAMP.

        Args:
            backup_id: int - the id of the backup to restore from

        Returns:
        Raises:
        """

        self._logger.debug("{func} - backup id |{backup_id}|".format(
                                                                    func="restore_backup",
                                                                    backup_id=backup_id))

        try:
            await server.Server.scheduler.queue_task(uuid.UUID(lib.SCHEDULE_RESTORE_ON_DEMAND))

            _message = self._MESSAGES_LIST["i000001"]
            Restore._logger.info("{0}".format(_message))

        except Exception as _ex:
            _message = self._MESSAGES_LIST["e000001"].format(_ex)
            Restore._logger.error("{0}".format(_message))

            raise exceptions.RestoreFailed(_message)


class RestoreProcess(FoglampProcess):
    """ Restore the entire FogLAMP repository.
    """

    _MODULE_NAME = "foglamp_restore_postgres_process"

    _logger = None

    _backup_id = None
    """ Used to store the optional command line parameter value """

    _file_name = None
    """ Used to store the optional command line parameter value """

    class FogLampStatus(object):
        """ FogLamp possible status """

        NOT_DEFINED = 0
        STOPPED = 1
        RUNNING = 2

    _FOGLAMP_CMD = "scripts/foglamp {0}"
    """ Command for managing FogLAMP, stop/start/status """

    _MESSAGES_LIST = {

        # Information messages
        "i000001": "Execution started.",
        "i000002": "Execution completed.",

        # Warning / Error messages
        "e000000": "general error",
        "e000001": "Invalid file name",
        "e000002": "cannot retrieve the configuration from the manager, trying retrieving from file "
                   "- error details |{0}|",
        "e000003": "cannot retrieve the configuration from file - error details |{0}|",
        "e000004": "cannot restore the backup, file doesn't exists - file name |{0}|",
        "e000006": "cannot start FogLAMP after the restore - error details |{0}|",
        "e000007": "cannot restore the backup, restarting FogLAMP - error details |{0}|",
        "e000008": "cannot identify FogLAMP status, the maximum number of retries has been reached "
                   "- error details |{0}|",
        "e000009": "cannot restore the backup, either a backup or a restore is already running - pid |{0}|",
        "e000010": "cannot retrieve the FogLamp status - error details |{0}|",
        "e000011": "cannot restore the backup, the selected backup doesn't exists - backup id |{0}|",
        "e000012": "cannot restore the backup, the selected backup doesn't exists - backup file name |{0}|",
    }
    """ Messages used for Information, Warning and Error notice """

    def __init__(self):

        super().__init__()

        if not self._logger:
            self._logger = logger.setup(self._MODULE_NAME,
                                        destination=_LOGGER_DESTINATION,
                                        level=_LOGGER_LEVEL)
        try:
            self._backup_id = super().get_arg_value("--backup-id")
            self._file_name = super().get_arg_value("--file")

        except Exception as _ex:

            _message = _MESSAGES_LIST["e000003"].format(_ex)
            _logger.exception(_message)

            raise exceptions.ArgumentParserError(_message)

        self._restore = Restore(self._storage)
        self._restore_lib = lib.BackupRestoreLib(self._storage, self._logger)

        self._job = lib.Job()

        # Creates the objects references used by the library
        lib._logger = self._logger
        lib._storage = self._storage

    def _identify_last_backup(self):
        """ Identifies latest executed backup either successfully executed (COMPLETED) or already RESTORED

        Args:
        Returns:
        Raises:
            NoBackupAvailableError: No backup either successfully executed or already restored available
            FileNameError: it is impossible to identify an unique backup to restore
        """

        self._logger.debug("{func} ".format(func="_identify_last_backup"))

        sql_cmd = """
            SELECT id, file_name FROM foglamp.backups WHERE (ts,id)=
            (SELECT  max(ts),MAX(id) FROM foglamp.backups WHERE status={0} or status={1});
        """.format(lib.BackupStatus.COMPLETED,
                   lib.BackupStatus.RESTORED)

        data = self._restore_lib.storage_retrieve(sql_cmd)

        if len(data) == 0:
            raise exceptions.NoBackupAvailableError

        elif len(data) == 1:
            _backup_id = data[0]['id']
            _file_name = data[0]['file_name']

        else:
            raise exceptions.FileNameError

        return _backup_id, _file_name

    def _identifies_backup_to_restore(self):
        """Identifies the backup to restore either
        - latest backup
        - or a specific backup_id
        - or a specific file_name

        Args:
        Returns:
        Raises:
            FileNotFoundError
        """

        backup_id = None
        file_name = None

        # Case - last backup
        if self._backup_id is None and \
           self._file_name is None:

            backup_id,  file_name = self._identify_last_backup()

        # Case - backup-id
        elif self._backup_id is not None:

            try:
                backup_info = self._restore_lib.get_backup_details(self._backup_id)
                backup_id = backup_info["id"]
                file_name = backup_info["file_name"]

            except exceptions.DoesNotExist:
                _message = self._MESSAGES_LIST["e000011"].format(self._backup_id)
                _logger.error(_message)

                raise exceptions.DoesNotExist(_message)

        # Case - file-name
        elif self._file_name is not None:

            try:
                backup_info = lib.get_backup_details_from_file_name(self._file_name)
                backup_id = backup_info["id"]
                file_name = backup_info["file_name"]

            except exceptions.DoesNotExist:
                _message = self._MESSAGES_LIST["e000012"].format(self._file_name)
                _logger.error(_message)

                raise exceptions.DoesNotExist(_message)

        if not os.path.exists(file_name):

            _message = self._MESSAGES_LIST["e000004"].format(file_name)
            _logger.error(_message)

            raise FileNotFoundError(_message)

        return backup_id, file_name

    def _foglamp_stop(self):
        """ Stops FogLAMP before for the execution of the backup, doing a cold backup

        Args:
        Returns:
        Raises:
            FogLAMPStopError
        """

        self._logger.debug("{func}".format(func="_foglamp_stop"))

        cmd = "{path}/{cmd}".format(
            path=self._restore_lib.dir_foglamp_root,
            cmd=self._FOGLAMP_CMD.format("stop")
        )

        # Stops FogLamp
        status, output = lib.exec_wait_retry(cmd, True,
                                             max_retry=self._restore_lib.config['max_retry'],
                                             timeout=self._restore_lib.config['timeout'])

        self._logger.debug("{func} - status |{status}| - cmd |{cmd}| - output |{output}|   ".format(
                    func="_foglamp_stop",
                    status=status,
                    cmd=cmd,
                    output=output))

        # FIXME: the check for status 123 is a temporary workaround as the stop is raising an error every time
        if status == 0 or status == 123:

            # Checks to ensure the FogLamp status
            if self._foglamp_status() != self.FogLampStatus.STOPPED:
                raise exceptions.FogLAMPStopError(output)
        else:
            raise exceptions.FogLAMPStopError(output)

    def _decode_foglamp_status(self, text):
        """
        Args:
        Returns:
        Raises:
        """

        if 'FogLAMP running.' in text:
            status = self.FogLampStatus.RUNNING

        elif 'FogLAMP not running.' in text:
            status = self.FogLampStatus.STOPPED

        else:
            status = self.FogLampStatus.NOT_DEFINED

        return status

    def _check_wait_foglamp_start(self):
        """ Checks and waits FogLAMP to start

        Args:
        Returns:
            status: FogLampStatus - {NOT_DEFINED|STOPPED|RUNNING}
        Raises:
        """

        self._logger.debug("{func}".format(func="_check_wait_foglamp_start"))

        status = self.FogLampStatus.NOT_DEFINED

        n_retry = 0
        max_reties = self._restore_lib.config['restart-max-retries']
        sleep_time = self._restore_lib.config['restart-sleep']

        while n_retry < max_reties:

            self._logger.debug("{func}".format(func="_check_wait_foglamp_start - checks FogLamp status"))

            status = self._foglamp_status()
            if status == self.FogLampStatus.RUNNING:
                break

            self._logger.debug("{func}".format(func="_check_wait_foglamp_start - sleep {0}".format(sleep_time)))

            time.sleep(sleep_time)
            n_retry += 1

        return status

    def _foglamp_status(self):
        """ Checks FogLAMP status

        to ensure the status is stable and reliable,
        It executes the FogLamp 'status' command until either
        until the same value comes back for 3 times in a row  or it reaches the maximum number of retries allowed.

        Args:
        Returns:
            status: FogLampStatus - {STATUS_NOT_DEFINED|STATUS_STOPPED|STATUS_RUNNING}
        Raises:
        """

        status = self.FogLampStatus.NOT_DEFINED

        num_exec = 0
        max_exec = 10
        same_status = 0
        same_status_ok = 3
        sleep_time = 1

        while (same_status < same_status_ok) and (num_exec <= max_exec):

            try:

                cmd = "{path}/{cmd}".format(
                            path=self._restore_lib.dir_foglamp_root,
                            cmd=self._FOGLAMP_CMD.format("status")
                )

                cmd_status, output = lib.exec_wait(cmd, True, _timeout=self._restore_lib.config['timeout'])

                self._logger.debug("{func} - output |{output}| \r - status |{status}|  ".format(
                                                                                            func="_foglamp_status",
                                                                                            output=output,
                                                                                            status=cmd_status))

                num_exec += 1

                new_status = self._decode_foglamp_status(output)

            except Exception as _ex:
                _message = self._MESSAGES_LIST["e000010"].format(_ex)
                _logger.error(_message)

                raise

            else:
                if new_status == status:
                    same_status += 1
                    time.sleep(sleep_time)
                else:
                    status = new_status
                    same_status = 0

        if num_exec >= max_exec:
            _message = self._MESSAGES_LIST["e000008"]
            self._logger.error(_message)

            status = self.FogLampStatus.NOT_DEFINED

        return status

    def _run_restore_command(self, backup_file):
        """ Executes the restore of the storage layer from a backup

        Args:
            backup_file: backup file to restore
        Returns:
        Raises:
            RestoreError
        """

        self._logger.debug("{func} - Restore starts - file name |{file}|".format(
                                                                    func="_run_restore_command",
                                                                    file=backup_file))

        # Prepares the restore command
        # FIXME:
        cmd = "{cmd} {options} -d {db}  {file}".format(
                                                cmd="pg_restore",
                                                options="--verbose --clean --no-acl --no-owner",
                                                db=self._restore_lib.config['database'],
                                                file=backup_file
        )

        # Restores the backup
        status, output = lib.exec_wait_retry(cmd, True, timeout=self._restore_lib.config['timeout'])

        # Avoid output too long
        output_short = output.splitlines()[10]

        self._logger.debug("{func} - Restore ends - status |{status}| - cmd |{cmd}| - output |{output}|".format(
                                    func="_run_restore_command",
                                    status=status,
                                    cmd=cmd,
                                    output=output_short))

        if status != 0:
            raise exceptions.RestoreFailed

    def _foglamp_start(self):
        """ Starts FogLAMP after the execution of the restore

        Args:
        Returns:
        Raises:
            FogLAMPStartError
        """

        cmd = "{path}/{cmd}".format(
                                    path=self._restore_lib.dir_foglamp_root,
                                    cmd=self._FOGLAMP_CMD.format("start")
        )

        exit_code, output = lib.exec_wait_retry(
                                                cmd,
                                                True,
                                                max_retry=self._restore_lib.config['max_retry'],
                                                timeout=self._restore_lib.config['timeout'])

        self._logger.debug("{func} - exit_code |{exit_code}| - cmd |{cmd}| - output |{output}|".format(
                                    func="_foglamp_start",
                                    exit_code=exit_code,
                                    cmd=cmd,
                                    output=output))

        if exit_code == 0:
            if self._check_wait_foglamp_start() != self.FogLampStatus.RUNNING:
                raise exceptions.FogLAMPStartError

        else:
            raise exceptions.FogLAMPStartError

    def execute_restore(self):
        """Executes the restore operation

        Args:
        Returns:
        Raises:
        """

        self._logger.debug("{func}".format(func="execute_restore"))

        backup_id, file_name = self._identifies_backup_to_restore()

        self._logger.debug("{func} - backup to restore |{id}| - |{file}| ".format(func="execute_restore",
                                                                                   id=backup_id,
                                                                                   file=file_name))

        # Stops FogLamp if it is running
        if self._foglamp_status() == self.FogLampStatus.RUNNING:
            self._foglamp_stop()

        self._logger.debug("{func} - FogLamp is down".format(func="execute_restore"))

        # Executes the restore and then starts Foglamp
        try:
            self._run_restore_command(file_name)

            # Updates the backup as restored
            self._restore_lib.backup_status_update(backup_id, lib.BackupStatus.RESTORED)

        except Exception as _ex:
            _message = self._MESSAGES_LIST["e000007"].format(_ex)

            self._logger.error(_message)
            raise

        finally:
            try:
                self._foglamp_start()

            except Exception as _ex:
                _message = self._MESSAGES_LIST["e000006"].format(_ex)

                self._logger.error(_message)
                raise

    def init(self):
        """"Setups the correct state for the execution of the restore

        Args:
        Returns:
        Raises:
        """

        self._logger.debug("{func}".format(func="init"))

        self._restore_lib.evaluate_paths()

        self._restore_lib.retrieve_configuration()

        # Checks for backup/restore synchronization
        pid = self._job.is_running()
        if pid == 0:

            # no job is running
            pid = os.getpid()
            self._job.set_as_running(lib.JOB_SEM_FILE_RESTORE, pid)
        else:
            _message = self._MESSAGES_LIST["e000009"].format(pid)
            self._logger.warning("{0}".format(_message))

            raise exceptions.BackupOrRestoreAlreadyRunning

    def shutdown(self):
        """"Sets the correct state to terminate the execution

        Args:
        Returns:
        Raises:
        """

        self._logger.debug("{func}".format(func="shutdown"))

        self._job.set_as_completed(lib.JOB_SEM_FILE_RESTORE)

    def run(self):
        """Restores a backup

        Args:
        Returns:
        Raises:
            exceptions.RestoreFailed
        """

        self.init()

        try:
            self.execute_restore()

        except Exception as _ex:
            _message = _MESSAGES_LIST["e000002"].format(_ex)
            _logger.error(_message)

            self.shutdown()

            raise exceptions.RestoreFailed(_message)
        else:
            self.shutdown()


if __name__ == "__main__":

    # Initializes the logger
    try:
        _logger = logger.setup(_MODULE_NAME,
                               destination=_LOGGER_DESTINATION,
                               level=_LOGGER_LEVEL)

    except Exception as ex:
        message = _MESSAGES_LIST["e000001"].format(str(ex))
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        print("[FOGLAMP] {0} - ERROR - {1}".format(current_time, message), file=sys.stderr)
        sys.exit(1)

    # Starts
    _logger.info(_MESSAGES_LIST["i000001"])

    # Initializes FoglampProcess and RestoreProcess classes - handling also the command line parameters
    try:
        restore_process = RestoreProcess()

    except Exception as ex:
        message = _MESSAGES_LIST["e000004"].format(ex)
        _logger.exception(message)

        _logger.info(_MESSAGES_LIST["i000002"])
        sys.exit(1)

    # Executes the Restore
    try:
        # Setup signals handlers, to avoid the termination of the restore
        # a) SIGINT: Keyboard interrupt
        # b) SIGTERM: kill or system shutdown
        # c) SIGHUP: Controlling shell exiting
        # noinspection PyUnresolvedReferences
        signal.signal(signal.SIGINT, _signal_handler)
        # noinspection PyUnresolvedReferences
        signal.signal(signal.SIGTERM, _signal_handler)
        # noinspection PyUnresolvedReferences
        signal.signal(signal.SIGHUP, _signal_handler)
        # noinspection PyUnresolvedReferences
        signal.signal(signal.SIGALRM, _signal_handler)

        # noinspection PyProtectedMember
        _logger.debug("{module} - name |{name}| - address |{addr}| - port |{port}| "
                      "- file |{file}| - backup_id |{backup_id}| ".format(
                                                                        module=_MODULE_NAME,
                                                                        name=restore_process._name,
                                                                        addr=restore_process._core_management_host,
                                                                        port=restore_process._core_management_port,
                                                                        file=restore_process._file_name,
                                                                        backup_id=restore_process._backup_id))

        restore_process.run()

        _logger.info(_MESSAGES_LIST["i000002"])
        sys.exit(0)

    except Exception as ex:
        message = _MESSAGES_LIST["e000002"].format(ex)
        _logger.exception(message)

        _logger.info(_MESSAGES_LIST["i000002"])
        sys.exit(1)
