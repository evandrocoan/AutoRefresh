import threading
import time
import sublime, sublime_plugin

refreshThreads = {}

def status(message, *formatting):
	print("Autorefresh:", message, " ".join( str( item ) for item in formatting ) )
	sublime.status_message(message)

#Enables autorefresh for the specified view
def enable_autorefresh_for_view(view):
    settings = sublime.load_settings('AutoRefresh.sublime-settings')
    refreshRate = settings.get('auto_refresh_rate')

    if refreshRate == None or not isinstance(refreshRate, (int, float)):
        status("Invalid auto_refresh_rate setting, using default 3")
        refreshRate = 3

    if refreshThreads.get(view.id()) is None or not refreshThreads.get(view.id()).enabled:
        refreshThreads[view.id()] = RefreshThread(view, refreshRate)
        refreshThreads[view.id()].start()

#Disables autorefresh for the specified view.
#Does nothing if autorefresh was already disabled
def disable_autorefresh_for_view(view):
    if refreshThreads.get(view.id()) != None:
        refreshThreads[view.id()].enabled = False


#Commands
class EnableAutoRefreshCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        enable_autorefresh_for_view(self.view)


class ToggleAutoRefreshCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        refreshThread = refreshThreads.get( view.id() )
        # print('refreshThread', refreshThread)

        if refreshThread and refreshThread.enabled:
            status('Disabling autorefresh for view', view.id())
            disable_autorefresh_for_view( view )

        else:
            status('Enabling autorefresh for view', view.id())
            enable_autorefresh_for_view( self.view )

class ReloadCurrentViewRefreshCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()

        if view.is_dirty():
            status("NOT Reloading current view because it is dirty!", refreshThreads)
        else:
            status("Reloading current view...", refreshThreads)
            view.run_command( 'revert' )

            # https://github.com/SublimeTextIssues/Core/issues/2239
            new_x = 0
            viewport_height = view.viewport_extent()[1]
            current_y_position = view.viewport_position()[1]

            # print("viewport_height: %s, current_y_position: %s" % (viewport_height, current_y_position))
            # if current_y_position > viewport_height:
            view.set_viewport_position((new_x, current_y_position), False)

class DisableAutoRefreshCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        disable_autorefresh_for_view(self.view)

class AutoRefreshRememberFileCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        curFileName = self.view.file_name()
        if curFileName is None:
            return

        settings = sublime.load_settings('AutoRefresh.sublime-settings')
        autoRefreshFiles = settings.get('files_with_auto_refresh_enabled_on_load')

        if autoRefreshFiles is None or not isinstance(autoRefreshFiles, (list)):
            autoRefreshFiles = []

        global refreshThreads
        refreshThreadForCurView = refreshThreads.get(self.view.id())
        if refreshThreadForCurView is not None and refreshThreadForCurView.enabled:
            #Autorefresh is currently enabled
            if curFileName not in autoRefreshFiles:
                autoRefreshFiles.append(curFileName)
        else:
            #Autorefresh is currently disabled
            if curFileName in autoRefreshFiles:
                autoRefreshFiles.remove(curFileName)

        settings.set('files_with_auto_refresh_enabled_on_load', autoRefreshFiles)


#Event handler for editor events
class SublimeEventHandler(sublime_plugin.EventListener):
    def on_pre_close(self, view):
        disable_autorefresh_for_view(view)

    def on_load(self, view):
        settings = sublime.load_settings('AutoRefresh.sublime-settings')
        autoRefreshFiles = settings.get('files_with_auto_refresh_enabled_on_load')

        if autoRefreshFiles is None or not isinstance(autoRefreshFiles, (list)):
            status("Invalid files_with_auto_refresh_enabled_on_load setting")
            autoRefreshFiles = []

        curFileName = view.file_name()
        if curFileName is not None and curFileName in autoRefreshFiles:
            enable_autorefresh_for_view(view)


#Threading class that continuously reloads a file
class RefreshThread(threading.Thread):
    def __init__(self, view, refreshRate):
        self.view = view
        self.enabled = True
        self.refreshRate = refreshRate
        threading.Thread.__init__(self)

    def run(self):
        while self.enabled:
            if not self.view.is_dirty(): #Don't reload if user made changes
                sublime.set_timeout(self.reloadFile, 1) #Reload file
                sublime.set_timeout(self.setView, 10)   #Wait for file reload to be finished
            #else:
                #self.enabled = False
            time.sleep(self.refreshRate)

    def reloadFile(self):
        row = self.view.rowcol(self.view.sel()[0].begin())[0] + 1
        rowCount = (self.view.rowcol(self.view.size())[0] + 1)

        if rowCount - row <= 3:
            self.moveToEOF = True
        else:
            self.moveToEOF = False
            #Sublime seems to have a bug where continuously reloading a file causes the viewport to scroll around
            #Any fixes to this problem seem to have no effect since viewport_position() returns an incorrect value causing the scrolling
            #What would probably work is to force focus on the cursor

        self.view.run_command('revert')

    def setView(self):
        if not self.view.is_loading():
            #Loading finished
            if self.moveToEOF:
                self.view.run_command("move_to", {"to": "eof", "extend": "false"})
        else:
            sublime.set_timeout(self.setView, 10)
