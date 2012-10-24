import sys
sys.path.insert(0, '../..')
from everpad.provider.service import ProviderService
from everpad.provider.sync import SyncThread
from everpad.provider.tools import set_auth_token, get_db_session
from everpad.tools import get_auth_token
from everpad.provider import models
from PySide.QtCore import QCoreApplication, Slot, QSettings
from PySide.QtGui import QDesktopServices
import dbus
import dbus.mainloop.glib
import signal
import fcntl
import os
import getpass
import argparse


class ProviderApp(QCoreApplication):
    def __init__(self, verbose, *args, **kwargs):
        QCoreApplication.__init__(self, *args, **kwargs)
        QCoreApplication.setOrganizationName('everpad')
        QCoreApplication.setApplicationName('everpad-provider')
        self.settings = QSettings()
        self.verbose = verbose
        session_bus = dbus.SessionBus()
        self.bus = dbus.service.BusName("com.everpad.Provider", session_bus)
        self.service = ProviderService(self, session_bus, '/EverpadProvider')
        self.sync_thread = SyncThread(self)
        self.sync_thread.sync_state_changed.connect(
            Slot(int)(self.service.sync_state_changed),
        )
        self.sync_thread.data_changed.connect(
            Slot()(self.service.data_changed),
        )
        if get_auth_token():
            self.sync_thread.start()
        self.service.qobject.authenticate_signal.connect(
            self.on_authenticated,
        )
        self.service.qobject.remove_authenticate_signal.connect(
            self.on_remove_authenticated,
        )

    @Slot(str)
    def on_authenticated(self, token):
        set_auth_token(token)
        self.sync_thread.start()

    @Slot()
    def on_remove_authenticated(self):
        self.sync_thread.quit()
        set_auth_token('')
        session = get_db_session()
        session.query(models.Note).delete(
            synchronize_session='fetch',
        )
        session.query(models.Resource).delete(
            synchronize_session='fetch',
        )
        session.query(models.Notebook).delete(
            synchronize_session='fetch',
        )
        session.query(models.Tag).delete(
            synchronize_session='fetch',
        )
        session.commit()

    def log(self, data):
        if self.verbose:
            print data


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    fp = open('/tmp/everpad-provider-%s.lock' % getpass.getuser(), 'w')
    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    try:
        dataDir = QDesktopServices.storageLocation(QDesktopServices.DataLocation)
        os.mkdir(os.path.expanduser('~/.everpad/'))
        os.mkdir(os.path.expanduser('~/.everpad/data/'))
    except OSError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help='verbose output')
    args = parser.parse_args(sys.argv[1:])
    app = ProviderApp(args.verbose, sys.argv)
    app.exec_()

if __name__ == '__main__':
    main()
