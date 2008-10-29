#!/usr/bin/env python
#
#    Limited command Shell (lshell)
#  
#    $Id: lshell.py,v 1.3 2008-10-29 22:39:46 ghantoos Exp $
#
#    "Copyright 2008 Ignace Mouzannar ( http://ghantoos.org )"
#    Email: ghantoos@ghantoos.org
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


import cmd
import sys
import os
import ConfigParser
from threading import Timer
from getpass import getpass, getuser
import termios
import string, re
import getopt

# Global Variable config_list listing the required configuration fields per user
config_list = ['allowed', 'forbidden', 'warning_counter', 'timer', 'scp', 'sftp']
LOGFILE='/var/log/lshell.log'
CONFIGFILE='/etc/lshell.conf'
HISTORY='.lhistory'

# help text
help = """Usage: lshell [options]

Options:
  -h|--help                         Show this help message
  -c|--config /path/to/config/file  Select config file 
                                    (default is /etc/lshell.conf)
  -l|--log    /path/to/logfile      Specify the logfile to use
                                    (default is /var/log/lshell.log)

"""

help_help = """Limited Shell (lshell) limited help.
Cheers.
"""

# Intro Text
intro = """------------------
Welcome to lshell!
------------------
Type '?' or 'help' to get the list of allowed commands"""

class shell_cmd(cmd.Cmd,object): 

	def __init__(self, userconf):
		self.conf = userconf
		self.log = log
		self.identchars = self.identchars + '+./-'
		if (self.conf['timer'] > 0): 
			t = Timer(2, self.mytimer)
			t.start()
		self.log('Logged in',self.conf['logfile'])
		self.history = os.path.normpath(self.conf['home_path'])+'/'+HISTORY
		cmd.Cmd.__init__(self)
		self.prompt = self.conf['username']+':~$ '
		self.intro = intro

	def __getattr__(self, attr):
		"""This method actually takes care of all the called method that are 
		not resolved (i.e not existing methods). It actually will simulate
		the existance of any method	entered in the 'allowed' variable list.

		e.g. You just have to add 'uname' in list of allowed commands in 
		the 'allowed' variable, and lshell will react as if you had 
		added a do_uname in the shell_cmd class!
		"""
		if self.check_secure(self.g_line) == 0: return object.__getattribute__(self, attr)
		if self.check_path(self.g_line) == 0: return object.__getattribute__(self, attr)
		if self.g_cmd in ['quit', 'exit', 'EOF']:
			self.log('Exited',self.conf['logfile'])
			self.stdout.write('\nExiting..\n')
			sys.exit(1)
		elif self.g_cmd in self.conf['allowed']:
			if self.g_cmd in ['cd']:
				if len ( self.g_arg ) >= 1:
					if os.path.isdir(self.g_arg): 
						os.chdir( self.g_arg )
						self.updateprompt(os.getcwd())
					else: self.stdout.write('No such directory.\n')
				else: 
					os.chdir(self.conf['home_path'])
					self.updateprompt(os.getcwd())
			else:
				os.system(self.g_line)
		elif self.g_cmd not in ['','?','help'] : 
			self.log('UNKW: '+self.g_line, self.conf['logfile'])
			self.stdout.write('*** Unknown syntax: %s\n'%self.g_cmd) 
		self.g_cmd, self.g_arg, self.g_line = ['', '', ''] 
		return object.__getattribute__(self, attr)

	def check_secure(self,line):
		"""This method is used to check the content on the typed command.
		Its purpose is to forbid the user to user to override the lshell
		command restrictions. 
		The forbidden characters are placed in the 'forbidden' variable.
		Feel free to update the list. Emptying it would be quite useless..: )

		A warining counter has been added, to kick out of lshell a user if he
		is warned more than X time (X beeing the 'forbidden_counter' variable).
		"""
		for item in self.conf['forbidden']:
			if item in line:
				self.conf['warning_counter'] -= 1
				if self.conf['warning_counter'] <= 0: 
					self.log('FIRED: '+self.g_line,self.conf['logfile'])
					self.stdout.write('I warned you.. See ya!\n')
					sys.exit(1)
				else:
					self.log('WARN: '+self.g_line,self.conf['logfile'])
					self.stdout.write('WARNING: What are you trying to do??\n')
				return 0

	def check_path(self, line):
		path_ = eval(str(self.conf['path']))
		for i in range(0,len(path_)):
			path_[i] = os.path.normpath(path_[i])
		path_re = string.join(path_,'.*|')
		if '/' in line:
			line = line.strip().split(' ')
			for item in line:
				if '/' in item:
					if item[0] == '/': tomatch = item
					else: tomatch = os.getcwd()+'/'+item
					if not re.findall(path_re,tomatch) : 
						self.check_secure(self.conf['forbidden'][0])
						return 0
		else:
			if not re.findall(path_re,os.getcwd()) : 
				self.conf['warning_counter'] -= 1
				if self.conf['warning_counter'] <= 0: 
					self.log('FIRED: '+self.g_line,self.conf['logfile'])
					self.stdout.write('I warned you.. See ya!\n')
					sys.exit(1)
				self.log('WARN: '+"CMD: '"+self.g_line+"' in '"+os.getcwd()+"'",self.conf['logfile'])
				self.stdout.write('You were not supposed to be here.\n')
				self.stdout.write('This incident will be reported\n')
				os.chdir(self.conf['home_path'])
				self.updateprompt(os.getcwd())
				return 0

	def updateprompt(self, path):
		if path is self.conf['home_path']:
			self.prompt = self.conf['username'] + ':~$ '
		elif re.findall(self.conf['home_path'], path) :
			self.prompt = self.conf['username'] + ':~' + path.split(self.conf['home_path'])[1] + '$ '
		else:
			self.prompt = self.conf['username'] + ':' + path + '$ '

	def cmdloop(self, intro=None):
		"""Repeatedly issue a prompt, accept input, parse an initial prefix
		off the received input, and dispatch to action methods, passing them
		the remainder of the line as argument.

		"""

		self.preloop()
		if self.use_rawinput and self.completekey:
			try:
				import readline
				try:
					readline.read_history_file(self.history)
				except IOError:
					# if history file does not exist
					open(self.history, 'w').close()
					readline.read_history_file(self.history)
				self.old_completer = readline.get_completer()
				readline.set_completer(self.complete)
				readline.parse_and_bind(self.completekey+": complete")
			except ImportError:
				pass
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
					import readline
					readline.set_completer(self.old_completer)
				except ImportError:
					pass
			readline.write_history_file(self.history)

	def complete(self, text, state):
		"""Return the next possible completion for 'text'.

		If a command has not been entered, then complete against command list.
		Otherwise try to call complete_<command> to get list of completions.
		"""
		if state == 0:
			import readline
			origline = readline.get_line_buffer()
			line = origline.lstrip()
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
		""" This method overrides the original default method. This method was originally used to
		warn when an unknown command was entered (*** Unknown syntax: blabla)
		It has been implemented in the __getattr__ method.
		So it has no use here. Its output is now empty.
		"""
		self.stdout.write('')

	def completenames(self, text, *ignored):
		""" This method overrides the original  completenames method to overload it's output
		with the command available in the 'allowed' variable
		This is useful when typing 'tab-tab' in the command prompt
		"""
		dotext = 'do_'+text
		names = self.get_names()
		for command in self.conf['allowed']: 
			names.append('do_' + command)
		return [a[3:] for a in names if a.startswith(dotext)]

	def completechdir(self,text, line, begidx, endidx):
		toreturn = []
		for instance in os.listdir(os.getcwd()):
			if os.path.isdir(instance):
				instance = instance+'/'
			toreturn.append(instance)

		return [a+' ' for a in toreturn if a.startswith(text)]

	def onecmd(self, line):
		""" This method overrides the original onecomd method, to put the cmd, arg and line 
		variables in class global variables: self.g_cmd, self.g_arg and self.g_line
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
		""" This method overrides the original emptyline method, so i doesn't repeat the 
		last command if last command was empty.
		I just found this annoying..
		"""
		if self.lastcmd:
			return 0

	def do_help(self, arg):
		""" This method overrides the original do_help method. Instead of printing out the
		that are documented or not, it returns the list of allowed commands when '?' or
		'help' is entered. Of course, it doesn't override the help function: any help_*
		method will be called (e.g. help_help(self) )
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
			# Get list of allowed commands, removes duplicate 'help' then sorts it
			list_tmp = dict.fromkeys(self.completenames('')).keys()
			list_tmp.sort()
			self.columnize(list_tmp)

	def help_help(self):
		self.stdout.write(help_help)

	def mytimer(self):
		""" This function is suppose to kick you out the the lshell after the 'timer' variable
		exprires. 'timer' is set in seconds.

		This function is still bugged as it creates a thread with the timer, then only kills 
		the thread and not the whole process.HELP!
		"""  
		self.stdout.write("Time's up! Exiting..\n")
		exit(0)


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

		self.log = log
		self.conf = {}
		self.conf, self.arguments = self.getoptions(args, self.conf)
		self.check_log()
		self.check_file(self.conf['configfile'])
		self.check_config_user(self.conf['configfile'])
		self.check_user_integrity()
		self.get_config_user()
		self.check_scp_sftp()
		self.check_passwd()

	def getoptions(self, arguments, conf):
		""" This method checks the usage. lshell.py must be called with a configuration file.
		If no configuration file is specified, it will set the configuration file path to 
		/etc/lshell.conf.
		"""
		# uncomment the following to set the -c or --config as mandatory argument
		#if '-c' not in arguments and '--config' not in arguments:
		#	usage()

		# set '/etc/lshell.conf' as default configuration file
		conf['configfile'] = CONFIGFILE
		conf['logfile'] = LOGFILE
		try:
			optlist, args = getopt.getopt(arguments, 'c:l:',['config=','log='])
		except getopt.GetoptError:
			self.usage()

		for option, value in optlist:
			if  option in ['-c', '--config']:
				conf['configfile'] = os.path.realpath(value)
			if  option in ['-l', '--log']:
				conf['logfile'] = os.path.realpath(value)
			elif option in ['-h', '--help']:
				self.usage()

		return conf, args

	def usage(self):
		""" Prints the usage """
		sys.stderr.write(help)
		sys.exit(0)

	def check_log(self):
		try:
			fp=open(self.conf['logfile'],'a').close()
		except IOError:
			self.conf['logfile']=''
			self.stderr.write('WARNING: Cannot write in log file: Permission denied.\n')
			self.stderr.write('WARNING: Actions will not be logged.\n')

	def check_file(self, config_file):
		""" This method checks the existence of the "argumently" given configuration file.
		"""
		if not os.path.exists(config_file): 
			self.stdout.write("Error: Config file doesn't exist\n")
			sys.exit(0)
		else: self.config = ConfigParser.ConfigParser()

	def check_config_user(self,config_file):
		""" This method checks if the current user exists in the configuration file.
		If the user is not found, he is exited from lshell.
		If the user is found, it continues by calling check_user_integrity() then check_passwd()
		"""
		self.config.read(config_file)
		self.user = getuser()
		if self.config.has_section(self.user) is False:
			if self.config.has_section('default') is False:
				self.stdout.write('Please check lshell\'s configuration file. It seem there is no default section\n')
				sys.exit(0)
			else: self.section = 'default'
		else:
			self.section = self.user

	def check_user_integrity(self):
		""" This method checks if all the required fields by user are present for the present user.
		In case fields are missing, the user is notified and exited from lshell
		"""
		quit = 0
		for item in config_list:
			if not self.config.has_option(self.section, item):
				if not self.config.has_option('default', item):
					self.stdout.write('Error: Missing parameter "' + item + '" for user ' + self.user + '\n')
					self.stdout.write('Error: Add it in the in the [user] or [default] section of conf file\n')
					sys.exit(0)

	def get_config_user(self):
		""" Once all the checks above have passed, the configuration files values are entered
		in a dict to be used by the command line it self. The lshell command line
		is then launched!
		"""
		for item in ['allowed','forbidden','warning_counter','timer','scp','sftp']:
			try:
				self.conf[item] = eval(self.config.get(self.user, item))
			except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
				self.conf[item] = eval(self.config.get('default', item))
		self.conf['username'] = self.user
		self.conf['allowed'].extend(['exit'])
		try:
			self.conf['home_path'] = os.path.normpath(eval(self.config.get(self.user, 'home_path')))
		except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
			self.conf['home_path'] = os.environ['HOME']
		try:
			self.conf['path'] = eval(self.config.get(self.user, 'path'))
		except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
			try:
				self.conf['path'] = eval(self.config.get('default', 'path'))
			except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
				self.conf['path'] = [self.conf['home_path']]
		try:
			self.conf['env_path'] = eval(self.config.get(self.user, 'env_path'))
		except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
			try:
				self.conf['env_path'] = eval(self.config.get('default', 'env_path'))
			except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
				self.conf['env_path'] = ''

		os.chdir(self.conf['home_path'])
		os.environ['PATH']=os.environ['PATH'] + self.conf['env_path']

	def check_scp_sftp(self):
		""" This method checks if the user is trying to SCP a file onto the server.
		If this is the case, it checks if the user is allowed to use SCP or not, and
		acts as requested. : )
		"""
		if len(self.arguments) > 1:
			if self.arguments[2].startswith('scp'):
				if self.conf['scp'] is 1: 
					if '&' not in self.arguments[2] and ';' not in self.arguments[2]:
						self.log('SCP: '+ str(self.arguments[2]),self.conf['logfile'])
						os.system(self.arguments[2])
						sys.exit(0)
					else:
						self.log('WARN_HACK?: '+ str(self.arguments[2]),self.conf['logfile'])
						self.stdout.write('\nWarning: This has been logged!\n')
						sys.exit(0)
				else:
					self.log('WARN_SCP: Not allowed -> '+ str(self.arguments[2]),self.conf['logfile'])
					self.stdout.write('Sorry..You are not allowed to use SCP.\n')
					sys.exit(0)
			elif 'sftp-server' in self.arguments[2]:
				if self.conf['sftp'] is 1:
					self.log('SFTP connect',self.conf['logfile'])
					os.system(self.arguments[2])
					self.log('SFTP disconnect',self.conf['logfile'])
					sys.exit(0)
				else:
					sys.exit(0)
			else:
				self.log('WARN_CMD_over_SSH: '+ str(self.arguments[2]),self.conf['logfile'])
				self.stdout.write('Sorry..You are not allowed to execute commands over ssh.\n')
				sys.exit(0)

	def check_passwd(self):
		""" As a passwd field is required by user. This method checks in the configuration file
		if the password is empty, in wich case, no passwrd check is required. In the other case,
		the password is asked to be entered.
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
				sys.exit(0)
		else: return 0

	def returnconf(self):
		return self.conf


def log(text,logfile):
	if logfile is not '':
		from time import strftime
		log = open(logfile, 'a')
		log.write(strftime("%Y-%m-%d %H:%M:%S") + ' ('+getuser()+'): ' + text + '\n')
		log.close()

if __name__=='__main__':

	try:
		userconf = check_config(sys.argv[1:])
		cli = shell_cmd(userconf.returnconf())
		cli.cmdloop()

	except (KeyboardInterrupt, EOFError):
		sys.stdout.write('\nExited on user request\n')
		sys.exit(0)

