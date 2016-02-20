import unittest
import os

# import lshell specifics
from lshell.shellcmd import ShellCmd
from lshell.checkconfig import CheckConfig
from lshell.utils import get_aliases
from lshell.variables import builtins_list
from lshell import builtins

TOPDIR = '%s/../' % os.path.dirname(os.path.realpath(__file__))


class TestFunctions(unittest.TestCase):
    args = ['--config=%s/etc/lshell.conf' % TOPDIR, "--quiet=1"]
    userconf = CheckConfig(args).returnconf()
    shell = ShellCmd(userconf, args)

    def test_01_checksecure_doublequote(self):
        """ U01 | quoted text should not be forbidden """
        INPUT = 'ls -E "1|2" tmp/test'
        return self.assertEqual(self.shell.check_secure(INPUT), 0)

    def test_02_checksecure_simplequote(self):
        """ U02 | quoted text should not be forbidden """
        INPUT = "ls -E '1|2' tmp/test"
        return self.assertEqual(self.shell.check_secure(INPUT), 0)

    def test_03_checksecure_doublepipe(self):
        """ U03 | double pipes should be allowed, even if pipe is forbidden """
        args = self.args + ["--forbidden=['|']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "ls || ls"
        return self.assertEqual(shell.check_secure(INPUT), 0)

    def test_04_checksecure_forbiddenpipe(self):
        """ U04 | forbid pipe, should return 1 """
        args = self.args + ["--forbidden=['|']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "ls | ls"
        return self.assertEqual(shell.check_secure(INPUT), 1)

    def test_05_checksecure_forbiddenchar(self):
        """ U05 | forbid character, should return 1 """
        args = self.args + ["--forbidden=['l']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "ls"
        return self.assertEqual(shell.check_secure(INPUT), 1)

    def test_06_checksecure_sudo_command(self):
        """ U06 | quoted text should not be forbidden """
        INPUT = "sudo ls"
        return self.assertEqual(self.shell.check_secure(INPUT), 1)

    def test_07_checksecure_notallowed_command(self):
        """ U07 | forbidden command, should return 1 """
        args = self.args + ["--allowed=['ls']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "ll"
        return self.assertEqual(shell.check_secure(INPUT), 1)

    def test_08_checkpath_notallowed_path(self):
        """ U08 | forbidden command, should return 1 """
        args = self.args + ["--path=['/home', '/var']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "cd /tmp"
        return self.assertEqual(shell.check_path(INPUT), 1)

    def test_09_checkpath_notallowed_path_completion(self):
        """ U09 | forbidden command, should return 1 """
        args = self.args + ["--path=['/home', '/var']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "cd /tmp/"
        return self.assertEqual(shell.check_path(INPUT, completion=1), 1)

    def test_10_checkpath_dollarparenthesis(self):
        """ U10 | when $() is allowed, return 0 if path allowed """
        args = self.args + ["--forbidden=[';', '&', '|','`','>','<', '${']"]
        userconf = CheckConfig(args).returnconf()
        shell = ShellCmd(userconf, args)
        INPUT = "echo $(echo aze)"
        return self.assertEqual(shell.check_path(INPUT), 0)

    def test_11_checkconfig_configoverwrite(self):
        """ U12 | forbid ';', then check_secure should return 1 """
        args = ['--config=%s/etc/lshell.conf' % TOPDIR, '--strict=123']
        userconf = CheckConfig(args).returnconf()
        return self.assertEqual(userconf['strict'], 123)

    def test_12_overssh(self):
        """ U12 | command over ssh """
        args = self.args + ["--overssh=['exit']", '-c exit']
        os.environ['SSH_CLIENT'] = '8.8.8.8 36000 22'
        if 'SSH_TTY' in os.environ:
            os.environ.pop('SSH_TTY')
        with self.assertRaises(SystemExit) as cm:
            CheckConfig(args).returnconf()
        return self.assertEqual(cm.exception.code, 0)

    def test_13_multiple_aliases_with_separator(self):
        """ U13 | multiple aliases using &&, || and ; separators """
        # enable &, | and ; characters
        aliases = {'foo': 'foo -l', 'bar': 'open'}
        INPUT = "foo; fooo  ;bar&&foo  &&   foo | bar||bar   ||     foo"
        return self.assertEqual(get_aliases(INPUT, aliases),
                                ' foo -l; fooo  ; open&& foo -l  '
                                '&& foo -l | open|| open   || foo -l')

    def test_14_sudo_all_commands_expansion(self):
        """ U14 | sudo_commands set to 'all' is equal to allowed variable """
        args = self.args + ["--sudo_commands=all"]
        userconf = CheckConfig(args).returnconf()
        # exclude internal and sudo(8) commands
        exclude = builtins_list + ['sudo']
        allowed = [x for x in userconf['allowed'] if x not in exclude]
        # sort lists to compare
        userconf['sudo_commands'].sort()
        allowed.sort()
        return self.assertEqual(allowed, userconf['sudo_commands'])

    def test_15_allowed_ld_preload_cmd(self):
        """ U15 | all allowed commands should be prepended with LD_PRELOAD """
        args = self.args + ["--allowed=['echo','export']"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare
        return self.assertEqual(userconf['aliases']['echo'],
                                'LD_PRELOAD=%s echo' % userconf['path_noexec'])

    def test_16_allowed_ld_preload_builtin(self):
        """ U16 | builtin commands should NOT be prepended with LD_PRELOAD """
        args = self.args + ["--allowed=['echo','export']"]
        userconf = CheckConfig(args).returnconf()
        # verify that export is not automatically added to the aliases (i.e.
        # prepended with LD_PRELOAD)
        return self.assertNotIn('export', userconf['aliases'])

    def test_17_allowed_exec_cmd(self):
        """ U17 | allowed_shell_escape should NOT be prepended with LD_PRELOAD
            The command should not be added to the aliases variable
        """
        args = self.args + ["--allowed_shell_escape=['echo']"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare
        return self.assertNotIn('echo', userconf['aliases'])

    def test_18_forbidden_environment(self):
        """ U18 | unsafe environment are forbidden
        """
        INPUT = 'export LD_PRELOAD=/lib64/ld-2.21.so'
        args = INPUT
        retcode = builtins.export(args)[0]
        return self.assertEqual(retcode, 1)

    def test_19_allowed_environment(self):
        """ U19 | other environment are accepted
        """
        INPUT = 'export MY_PROJECT_VERSION=43'
        args = INPUT
        retcode = builtins.export(args)[0]
        return self.assertEqual(retcode, 0)

    def test_20_winscp_allowed_commands(self):
        """ U20 | when winscp is enabled, new allowed commands are automatically
            added (see man).
        """
        args = self.args + ["--allowed=[]", "--winscp=1"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare, except 'export'
        exclude = list(set(builtins_list) - set(['export']))
        expected = exclude + ['scp', 'env', 'pwd', 'groups',
                              'unset', 'unalias']
        expected.sort()
        allowed = userconf['allowed']
        allowed.sort()
        return self.assertEqual(allowed, expected)

    def test_21_winscp_allowed_semicolon(self):
        """ U21 | when winscp is enabled, use of semicolon is allowed """
        args = self.args + ["--forbidden=[';']", "--winscp=1"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare
        return self.assertNotIn(';', userconf['forbidden'])

if __name__ == "__main__":
    unittest.main()
