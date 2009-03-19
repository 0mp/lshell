#!/usr/bin/env python
#
#    Limited command Shell (lshell)
#  
#    $Id: lshell.py,v 1.25 2009-03-19 00:02:29 ghantoos Exp $
#
#    "Copyright 2008 Ignace Mouzannar ( http://ghantoos.org )"
#    Email: ghantoos@ghantoos.org
#
#    This program is free software: you can redistribute it and/or modify      \
#    it under the terms of the GNU General Public License as published by      \
#    the Free Software Foundation, either version 3 of the License, or         \
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,           \
#    but WITHOUT ANY WARRANTY; without even the implied warranty of            \
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             \
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License         \
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


import cmd
import sys
import os
import ConfigParser
from getpass import getpass, getuser
import termios
import string
import re
import getopt
import logging
import signal
import readline
import grp

__author__ = "Ignace Mouzannar -ghantoos- <ghantoos@ghantoos.org>"
__version__= "0.9.0"

# Required config variable list per user
required_config = ['allowed', 'forbidden', 'warning_counter'] 
#                                                    'timer', 'scp', 'sftp']

# set configuration file path depending on sys.exec_prefix
# on *Linux sys.exec_prefix = '/usr' and default path must be in '/etc'
# on *BSD sys.exec_prefix = '/usr/{pkg,local}/' and default path 
# is '/usr/{pkg,local}/etc'
if sys.exec_prefix != '/usr':
    # for *BSD
    conf_prefix = sys.exec_prefix
else:
    # for *Linux
    conf_prefix = ''
CONFIGFILE = conf_prefix + '/etc/lshell.conf'

# history file
HISTORY = ".lhistory"

# help text
help = """Usage: lshell [OPTIONS]
  --config <file> : Config file location (default %s)
  --log    <dir>  : Log files directory
  -h, --help      : Show this help message
  --version       : Show version
""" % CONFIGFILE

help_help = """Limited Shell (lshell) limited help.
Cheers.
"""

# Intro Text
intro = """You are in a limited shell.
Type '?' or 'help' to get the list of allowed commands"""

class shell_cmd(cmd.Cmd,object): 
    """ Main lshell CLI class
    """

    def __init__(self, userconf):
        self.conf = userconf
        self.log = self.conf['logpath']
        # Set timer
        if self.conf['timer'] > 0: self.mytimer(self.conf['timer'])
        self.identchars = self.identchars + '+./-'
        self.log.error('Logged in')
        self.history = os.path.normpath(self.conf['home_path']) + '/' + HISTORY
        cmd.Cmd.__init__(self)
        self.prompt = self.conf['username'] + ':~$ '
        self.intro = intro

    def __getattr__(self, attr):
        """This method actually takes care of all the called method that are   \
        not resolved (i.e not existing methods). It actually will simulate     \
        the existance of any method    entered in the 'allowed' variable list. \

        e.g. You just have to add 'uname' in list of allowed commands in       \
        the 'allowed' variable, and lshell will react as if you had            \
        added a do_uname in the shell_cmd class!
        """
        if self.g_cmd in ['quit', 'exit', 'EOF']:
            self.log.error('Exited')
            if self.g_cmd == 'EOF':
                self.stdout.write('\n')
            sys.exit(0)
        if self.check_secure(self.g_line) == 1: 
            return object.__getattribute__(self, attr)
        if self.check_path(self.g_line) == 1:
            return object.__getattribute__(self, attr)
        if self.g_cmd in self.conf['allowed']:
            if self.g_cmd in ['cd']:
                if len(self.g_arg) >= 1:
                    if os.path.isdir(os.path.realpath(self.g_arg)): 
                        os.chdir(os.path.realpath(self.g_arg))
                        self.updateprompt(os.getcwd())
                    else: self.stdout.write('cd: %s: No such directory.\n'     \
                                                % os.path.realpath(self.g_arg))
                else: 
                    os.chdir(self.conf['home_path'])
                    self.updateprompt(os.getcwd())
            else:
                os.system(self.g_line)
        elif self.g_cmd not in ['','?','help',None] : 
            self.log.warn('INFO: unknown syntax -> "%s"' %self.g_line)
            self.stdout.write('*** unknown syntax: %s\n' %self.g_cmd)
        self.g_cmd, self.g_arg, self.g_line = ['', '', ''] 
        return object.__getattribute__(self, attr)

    def check_secure(self,line):
        """This method is used to check the content on the typed command.      \
        Its purpose is to forbid the user to user to override the lshell       \
        command restrictions. 
        The forbidden characters are placed in the 'forbidden' variable.
        Feel free to update the list. Emptying it would be quite useless..: )

        A warining counter has been added, to kick out of lshell a user if he  \
        is warned more than X time (X beeing the 'warning_counter' variable).
        """
        for item in self.conf['forbidden']:
            if item in line:
                self.counter_update('synthax')
                return 1

        # in case ';', '|' or '&' are not forbidden, check if in line
        lines = re.split('&|\||;', line)
        for sperate_line in lines:
            command = sperate_line.strip().split(' ')[0]
            if command not in self.conf['allowed'] and command != "":
                if len(lines) > 1:
                    self.counter_update('command', line)
                    return 1
                return 0
         
    def counter_update(self, messagetype, path=None):
        """ Update the warning_counter, log and display a warning to the user
        """
        self.conf['warning_counter'] -= 1
        if path:
            line = path
        else:
            line = self.g_line
        if self.conf['warning_counter'] <= 0: 
            self.log.critical('*** forbidden %s -> "%s"'                       \
                                                  % (messagetype ,line))
            self.log.critical('- Kicked out -')
            sys.exit(1)
        else:
            self.log.critical('*** forbidden %s -> "%s"'                       \
                                                  % (messagetype ,line))
            self.stdout.write('*** You have %s joker(s) left,'                 \
                                ' before getting kicked out.\n'                \
                                %(self.conf['warning_counter']-1))
            self.stdout.write('This incident has been reported.\n')

    def check_path(self, line, completion=0):
        """ Check if a path is entered in the line. If so, it checks if user   \
        are allowed to see this path. If user is not allowed, it calls         \
        self.counter_update. I case of completion, it only returns 0 or 1.
        """

        allowed_path_re = str(self.conf['path'][0])
        denied_path_re = str(self.conf['path'][1][:-1])

        if completion == 1:
            line = line.strip().split()
        else:
            line = line.strip().split()[1:]

        for item in line:
            tomatch = os.path.realpath(item) + '/'
            if os.path.exists(tomatch):
                match_allowed = re.findall(allowed_path_re,tomatch)
                if denied_path_re != '': 
                    match_denied = re.findall(denied_path_re,tomatch)
                else: match_denied = None
                if not match_allowed or match_denied:
                        if completion == 0:
                            self.counter_update('path', tomatch[:-1])
                        return 1
        if completion == 0:
            if not re.findall(allowed_path_re,os.getcwd()+'/'): 
                self.counter_update('path', os.getcwd())
                os.chdir(self.conf['home_path'])
                self.updateprompt(os.getcwd())
                return 1
        return 0

    def updateprompt(self, path):
        if path is self.conf['home_path']:
            self.prompt = self.conf['username'] + ':~$ '
        elif re.findall(self.conf['home_path'], path) :
            self.prompt = self.conf['username'] + ':~'                         \
                                + path.split(self.conf['home_path'])[1] + '$ '
        else:
            self.prompt = self.conf['username'] + ':' + path + '$ '

    def cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix    \
        off the received input, and dispatch to action methods, passing them   \
        the remainder of the line as argument.
        """

        self.preloop()
        if self.use_rawinput and self.completekey:
            try:
                readline.read_history_file(self.history)
            except IOError:
                # if history file does not exist
                try:
                    open(self.history, 'w').close()
                    readline.read_history_file(self.history)
                except IOError:
                    pass
            self.old_completer = readline.get_completer()
            readline.set_completer(self.complete)
            readline.parse_and_bind(self.completekey+": complete")
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write(str(self.intro)+"\n")
            stop = None
            while not stop:
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    if self.use_rawinput:
                        try:
                            line = raw_input(self.prompt)
                        except EOFError:
                            line = 'EOF'
                        except KeyboardInterrupt:
                            self.stdout.write('\n')
                            line = ''

                    else:
                        self.stdout.write(self.prompt)
                        self.stdout.flush()
                        line = self.stdin.readline()
                        if not len(line):
                            line = 'EOF'
                        else:
                            line = line[:-1] # chop \n
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            self.postloop()
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    readline.set_completer(self.old_completer)
                except ImportError:
                    pass
            try:
                readline.write_history_file(self.history)
            except IOError:
                self.log.error('WARN: couldn\'t write history '
                                                'to file %s\n' %self.history)

    def complete(self, text, state):
        """Return the next possible completion for 'text'.
        If a command has not been entered, then complete against command list. 
        Otherwise try to call complete_<command> to get list of completions.
        """
        if state == 0:
            origline = readline.get_line_buffer()
            line = origline.lstrip()
            # in case '|', ';', '&' used, take last part of line to complete
            line = re.split('&|\||;',line)[-1].lstrip()
            stripped = len(origline) - len(line)
            begidx = readline.get_begidx() - stripped
            endidx = readline.get_endidx() - stripped
            if line.split(' ')[0] in self.conf['allowed']:
                compfunc = self.completechdir
            elif begidx>0:
                cmd, args, foo = self.parseline(line)
                if cmd == '':
                    compfunc = self.completedefault
                else:
                    try:
                        compfunc = getattr(self, 'complete_' + cmd)
                    except AttributeError:
                        compfunc = self.completedefault
            else:
                compfunc = self.completenames
            self.completion_matches = compfunc(text, line, begidx, endidx)
        try:
            return self.completion_matches[state]
        except IndexError:
            return None

    def default(self, line):
        """ This method overrides the original default method. 
        It was originally used to warn when an unknown command was entered     \
        (e.g. *** Unknown syntax: blabla). 
        It has been implemented in the __getattr__ method.
        So it has no use here. Its output is now empty.
        """
        self.stdout.write('')

    def completenames(self, text, *ignored):
        """ This method overrides the original completenames method to overload\
        it's output with the command available in the 'allowed' variable       \
        This is useful when typing 'tab-tab' in the command prompt
        """
        dotext = 'do_'+text
        names = self.get_names()
        for command in self.conf['allowed']: 
            names.append('do_' + command)
        return [a[3:] for a in names if a.startswith(dotext)]

    def completechdir(self,text, line, begidx, endidx):
        toreturn = []
        try:
            directory = os.path.realpath(line.split()[-1])
        except: 
            directory = os.getcwd()

        if not os.path.isdir(directory):
            directory = directory.rsplit('/',1)[0]
            if directory == '': directory = '/'
            if not os.path.isdir(directory):
                directory = os.getcwd()

        if self.check_path(directory, 1) == 0:
            for instance in os.listdir(directory):
                if os.path.isdir(os.path.join(directory,instance)):
                    instance = instance + '/'
                else: instance = instance + ' '
                if instance.startswith('.'):
                    if text.startswith('.'):
                        toreturn.append(instance)
                    else: pass
                else: toreturn.append(instance)
            return [a for a in toreturn if a.startswith(text)]
        else:
            return None

    def onecmd(self, line):
        """ This method overrides the original onecomd method, to put the cmd, \
        arg and line variables in class global variables: self.g_cmd,          \
        self.g_arg and self.g_line.
        Thos variables are then used by the __getattr__ method
        """
        cmd, arg, line = self.parseline(line)
        self.g_cmd, self.g_arg, self.g_line = [cmd, arg, line] 
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if cmd == '':
            return self.default(line)
        else:
            try:
                func = getattr(self, 'do_' + cmd)
            except AttributeError:
                return self.default(line)
            return func(arg)

    def emptyline(self):
        """ This method overrides the original emptyline method, so it doesn't \
        repeat the last command if last command was empty.
        I just found this annoying..
        """
        if self.lastcmd:
            return 0

    def do_help(self, arg):
        """ This method overrides the original do_help method. 
        Instead of printing out the that are documented or not, it returns the \
        list of allowed commands when '?' or 'help' is entered. 
        Of course, it doesn't override the help function: any help_* method    \
        will be called (e.g. help_help(self) )
        """ 
        if arg:
            try:
                func = getattr(self, 'help_' + arg)
            except AttributeError:
                try:
                    doc=getattr(self, 'do_' + arg).__doc__
                    if doc:
                        self.stdout.write("%s\n"%str(doc))
                        return
                except AttributeError:
                    pass
                self.stdout.write("%s\n"%str(self.nohelp % (arg,)))
                return
            func()
        else:
            # Get list of allowed commands, remove duplicate 'help' then sort it
            list_tmp = dict.fromkeys(self.completenames('')).keys()
            list_tmp.sort()
            self.columnize(list_tmp)

    def help_help(self):
        self.stdout.write(help_help)

    def mytimer(self,timeout):
        """ This function is kicks you out the the lshell after      \
        the 'timer' variable exprires. 'timer' is set in seconds.
        """ 
        # set timer
        signal.signal(signal.SIGALRM, self._timererror)
        signal.alarm(self.conf['timer'])

    def _timererror(self, signum, frame):
        raise LshellTimeOut, "lshell timer timeout"

class check_config:

    def __init__(self, args, stdin=None, stdout=None, stderr=None):
        """ Force the calling of the methods below
        """ 
        if stdin is None:
            self.stdin = sys.stdin
        else:
            self.stdin = stdin
        if stdout is None:
            self.stdout = sys.stdout
        else:
            self.stdout = stdout
        if stderr is None:
            self.stderr = sys.stderr
        else:
            self.stderr = stderr

        self.conf = {}
        self.conf, self.arguments = self.getoptions(args, self.conf)
        self.check_file(self.conf['configfile'])
        self.get_global()
        self.check_log()
        self.get_config()
        self.check_user_integrity()
        self.get_config_user()
        self.check_scp_sftp()
        self.check_passwd()

    def getoptions(self, arguments, conf):
        """ This method checks the usage. lshell.py must be called with a      \
        configuration file.
        If no configuration file is specified, it will set the configuration   \
        file path to /etc/lshell.conf.
        """
        # uncomment the following to set the -c/--config as mandatory argument
        #if '-c' not in arguments and '--config' not in arguments:
        #    usage()

        # set CONFIGFILE as default configuration file
        conf['configfile'] = CONFIGFILE

        try:
            optlist, args = getopt.getopt(arguments,                           \
                                    'hc:',                                     \
                                    ['config=','log=','help','version'])
        except getopt.GetoptError:
            self.stderr.write('Missing or unknown argument(s)\n')
            self.usage()


        for option, value in optlist:
            if  option in ['--config']:
                conf['configfile'] = os.path.realpath(value)
            if  option in ['--log']:
                conf['logpath'] = os.path.realpath(value)
            if  option in ['-c']:
                conf['ssh'] = value
            if option in ['-h', '--help']:
                self.usage()
            if option in ['--version']:
                self.version()

        # put the expanded path of configfile and logpath (if exists) in 
        # LSHELL_ARGS environment variable
        args = ['--config', conf['configfile']]
        if conf.has_key('logpath'): args += ['--log', conf['logpath']]
        os.environ['LSHELL_ARGS'] = str(args)

        return conf, args

    def usage(self):
        """ Prints the usage """
        sys.stderr.write(help)
        sys.exit(0)

    def version(self):
        """ Prints the version """
        sys.stderr.write('lshell-%s - Limited Shell\n' %__version__)
        sys.exit(0)

    def check_file(self, config_file):
        """ This method checks the existence of the "argumently" given         \
        configuration file.
        """
        if not os.path.exists(config_file): 
            self.stdout.write("Error: Config file doesn't exist\n")
            self.stdout.write(help)
            sys.exit(0)
        else: self.config = ConfigParser.ConfigParser()

    def get_global(self):
        """ Loads the [global] parameters from the configuration file 
        """
        self.config.read(self.conf['configfile'])
        if not self.config.has_section('global'):
            self.stdout.write('Config file missing [global] section\n')
            sys.exit(0)

        for item in self.config.items('global'):
            if not self.conf.has_key(item[0]):
                self.conf[item[0]] = item[1]

        # log level must be 1, 2, 3  or 0
        if not self.conf.has_key('loglevel'): self.conf['loglevel'] = 0
        self.conf['loglevel'] = int(self.conf['loglevel'])
        if self.conf['loglevel'] > 3: self.conf['loglevel'] = 3
        elif self.conf['loglevel'] < 0: self.conf['loglevel'] = 0

    def check_log(self):
        """ Sets the log level and log file 
        """
        # define log levels dict
        levels = { 1 : logging.CRITICAL, 
                   2 : logging.ERROR, 
                   3 : logging.WARNING }

        # create logger for lshell application
        logger = logging.getLogger('lshell')
        formatter = logging.Formatter('%(asctime)s (' + getuser() \
                                                        + '): %(message)s')

        # set log to output error on stderr
        logsterr = logging.StreamHandler()
        logger.addHandler(logsterr)
        logsterr.setFormatter(logging.Formatter('%(message)s'))
        logsterr.setLevel(logging.CRITICAL)

        if self.conf['loglevel'] > 0:
            try:
                # if log file is writable add new log file handler
                logfile = self.conf['logpath'] + '/' + getuser() + '.log'
                fp=open(logfile,'a').close()
                logfile = logging.FileHandler(logfile)
                logger.addHandler(logfile)
                logfile.setFormatter(formatter)
                logfile.setLevel(levels[self.conf['loglevel']])

            except IOError:
                # uncomment the 2 following lines to warn if log file is not   \
                # writable 
                #sys.stderr.write('Warning: Cannot write in log file: '
                #                                        'Permission denied.\n')
                #sys.stderr.write('Warning: Actions will not be logged.\n')
                pass

        self.conf['logpath'] = logger
        self.log = logger

    def get_config(self):
        """ Load default, group and user configuation. Then merge them all. 
        The loadpriority is done in the following order:
            1- User section
            2- Group section
            3- Default section
        """
        self.config.read(self.conf['configfile'])
        self.user = getuser()

        self.conf_raw = {}

        # get 'default' configuration if any
        self.get_config_sub('default')

        # get groups configuration if any.
        # for each group the user belongs to, check if specific configuration  \
        # exists.  The primary group has the highest priority. 
        grplist = os.getgroups()
        grplist.reverse()
        for gid in grplist:
            grpname = grp.getgrgid(gid)[0]
            section = 'grp:' + grpname
            self.get_config_sub(section)

        # get user configuration if any
        self.get_config_sub(self.user)

        #print self.conf_raw

    def get_config_sub(self, section):
        """ self.get_config sub function """
        if self.config.has_section(section):
            for item in self.config.items(section):
                key = item[0]
                value = item[1]
                split = re.split('([\+\-\s]+\[[^\]]+\])',value.replace(' ',''))
                if len(split) > 1 and key in ['path',                          \
                                              'overssh',                       \
                                              'allowed',                       \
                                              'forbidden']:
                    for stuff in split:
                        if stuff.startswith('-') or stuff.startswith('+'):
                            self.conf_raw.update(self.minusplus(self.conf_raw, \
                                                                    key,stuff))
                        elif stuff == "'all'":
                            self.conf_raw.update({key:self.expand_all()})
                        elif stuff != '' and key == 'path':
                            liste = ['','']
                            for path in eval(stuff):
                                liste[0] += os.path.realpath(path) + '/.*|'
                            liste[0] = liste[0]
                            self.conf_raw.update({key:str(liste)})
                        elif stuff != '' and type(eval(stuff)) is list:
                            self.conf_raw.update({key:stuff})
                # case allowed is set to 'all'
                elif key == 'allowed' and split[0] == "'all'":
                    self.conf_raw.update({key:self.expand_all()})
                elif key == 'path':
                    liste = ['','']
                    for path in self.myeval(value, 'path'):
                        liste[0] += os.path.realpath(path) + '/.*|'
                    liste[0] = liste[0]
                    self.conf_raw.update({key:str(liste)})
                else:
                    self.conf_raw.update(dict([item]))

    def minusplus(self,confdict, key, extra):
        """ update configuration lists containing -/+ operators
        """
        if confdict.has_key(key):
            liste = self.myeval(confdict[key])
        elif key == 'path':
            liste = ['','']
        else:
            liste = []

        sublist = self.myeval(extra[1:],key)
        if extra.startswith('+'):
            if key == 'path':
                for path in sublist:
                    liste[0] += os.path.realpath(path) + '/.*|' 
            else:
                for item in sublist:
                    liste.append(item)
        elif extra.startswith('-'):
            if key == 'path':
                for path in sublist:
                    liste[1] += os.path.realpath(path) + '/.*|'
                liste[1] = liste[1]
            else:
                for item in sublist:
                    if item in liste:
                        liste.remove(item)
                    else:
                        self.log.error("CONF: -['%s'] ignored in '%s' list."   \
                                                                 %(item,key))
        return {key:str(liste)}
            

    def expand_all(self):
        """ expand allowed, if set to 'all'
        """
        expanded_all = []
        for directory in os.environ['PATH'].split(':'):
            if os.path.exists(directory):
                for item in os.listdir(directory):
                    if os.access(os.path.join(directory,item), os.X_OK):
                        expanded_all.append(item)
            else: self.log.error('CONF: PATH entry "%s" does not exist'        \
                                                                    % directory)
        return str(expanded_all)
 
    def myeval(self, value, info=''):
        try:
            evaluated = eval(value)
            return evaluated
        except SyntaxError:
            self.log.critical('CONF: Incomplete %s field in configuration file'\
                                                            % info)
            sys.exit(1)

    def check_user_integrity(self):
        """ This method checks if all the required fields by user are present  \
        for the present user.
        In case fields are missing, the user is notified and exited from lshell.
        """
        for item in required_config:
            if item not in self.conf_raw.keys():
                self.log.critical('ERROR: Missing parameter \'' \
                                                        + item + '\'')
                self.log.critical('ERROR: Add it in the in the [%s] '
                                    'or [default] section of conf file.'
                                    % self.user)
                sys.exit(0)

    def get_config_user(self):
        """ Once all the checks above have passed, the configuration files     \
        values are entered in a dict to be used by the command line it self.
        The lshell command line is then launched!
        """
        for item in ['allowed',
                    'forbidden',
                    'warning_counter',
                    'timer',
                    'scp',
                    'sftp',
                    'overssh']:
            try:
                self.conf[item] = self.myeval(self.conf_raw[item],item)
            except KeyError:
                self.conf[item] = 0
            except TypeError:
                self.log.critical('ERR: in the -%s- field. Check the'          \
                                  ' configuration file.' %item )
                sys.exit(0)

        self.conf['username'] = self.user

        try:
            self.conf['home_path'] = os.path.normpath(self.myeval(self.conf_raw\
                                                    ['home_path'],'home_path'))
            if not os.path.isdir(self.conf['home_path']):
                self.log.critical('CONF: home_path does not exist')
                sys.exit(0)
        except KeyError:
            self.conf['home_path'] = os.environ['HOME']

        try:
            self.conf['path'] = eval(self.conf_raw['path'])
            self.conf['path'][0] += self.conf['home_path'] + '.*'
        except KeyError:
            self.conf['path'] = ['','']
            self.conf['path'][0] = self.conf['home_path'] + '.*'

        try:
            self.conf['env_path'] = self.myeval(self.conf_raw['env_path'],     \
                                                                    'env_path')
        except KeyError:
            self.conf['env_path'] = ''

        os.chdir(self.conf['home_path'])
        os.environ['PATH']=os.environ['PATH'] + self.conf['env_path']

        self.conf['allowed'].append('exit')

    def check_scp_sftp(self):
        """ This method checks if the user is trying to SCP a file onto the    \
        server. If this is the case, it checks if the user is allowed to use   \
        SCP or not, and    acts as requested. : )
        """
        if self.conf.has_key('ssh'):
            if os.environ.has_key('SSH_CLIENT')                                \
                                        and not os.environ.has_key('SSH_TTY'):
                # case no tty is given to the session (sftp, scp, cmd over ssh)
                if self.conf['ssh'].find('&') > -1                             \
                            or self.conf['ssh'].find(';') > -1:
                    self.log.critical('*** forbidden char over ssh -> "%s"' 
                                                            %self.conf['ssh'])
                    self.stdout.write('This incident has been reported.\n')
                    sys.exit(0)
                if self.conf['ssh'].startswith('scp ')                         \
                                                and self.conf['scp'] is 1: 
                    if ' -f ' in self.conf['ssh']:
                        self.log.error('SCP: GET "%s"' %self.conf['ssh'])
                    elif ' -t ' in self.conf['ssh']:
                        self.log.error('SCP: PUT "%s"' %self.conf['ssh'])
                    os.system(self.conf['ssh'])
                    self.log.error('SCP disconnect')
                    sys.exit(0)
                elif 'sftp-server' in self.conf['ssh']                         \
                                                and self.conf['sftp'] is 1:
                    self.log.error('SFTP connect')
                    os.system("SHELL=/usr/bin/lshell " + self.conf['ssh'])
                    self.log.error('SFTP disconnect')
                    sys.exit(0)
                elif self.conf['ssh'].split()[0] in self.conf['overssh']:
                    self.log.error('Over SSH: "%s"' %self.conf['ssh'])
                    os.system(self.conf['ssh'])
                    self.log.error('Exited')
                    sys.exit(0)
                else:
                    self.log.critical('*** forbidden command over SSH: "%s"'   \
                                                            %self.conf['ssh'])
                    self.stdout.write('This incident has been reported.\n')
                    sys.exit(0)
            else :
                # case of shell escapes
                self.log.critical('*** forbidden shell escape: "%s"'           \
                                                            %self.conf['ssh'])
                self.stdout.write('This incident has been reported.\n')
                sys.exit(0)

    def check_passwd(self):
        """ As a passwd field is required by user. This method checks in the   \
        configuration file if the password is empty, in wich case, no password \
        check is required. In the other case, the password is asked to be      \
        entered. 
        If the entered password is wrong, the user is exited from lshell.
        """
        if self.config.has_section(self.user):
            if self.config.has_option(self.user, 'passwd'):
                passwd = self.config.get(self.user, 'passwd')
            else: 
                passwd = None
        else: 
            passwd = None

        if passwd:
            password = getpass("Enter "+self.user+"'s password: ")
            if password != passwd:
                self.stdout.write('Error: Wrong password \nExiting..\n')
                self.log.critical('WARN: Wrong password')
                sys.exit(0)
        else: return 0

    def returnconf(self):
        return self.conf

class LshellTimeOut(Exception):
    """ Custum exception used for timer timeout
    """

    def __init__(self, value = "Timed Out"):
        self.value = value
    def __str__(self):
        return repr(self.value)

def main():
    # set SHELL and get LSHELL_ARGS env variables
    os.environ['SHELL'] = os.path.realpath(sys.argv[0])
    if os.environ.has_key('LSHELL_ARGS'):
        args = sys.argv[1:] + eval(os.environ['LSHELL_ARGS'])
    else: args = sys.argv[1:]

    userconf = check_config(args).returnconf()

    try:
        cli = shell_cmd(userconf)
        cli.cmdloop()

    except (KeyboardInterrupt, EOFError):
        sys.stdout.write('\nExited on user request\n')
        sys.exit(0)
    except LshellTimeOut:
        userconf['logpath'].error('Timer expired')
        sys.stdout.write('\nTime is up.\n')

if __name__ == '__main__':
    main()


