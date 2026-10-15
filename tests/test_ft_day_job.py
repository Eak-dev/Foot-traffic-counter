"""Finite whole-day supervisor contracts, synthetic processes only."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch

from tools import ft_day_job as job


class WholeJobTests(unittest.TestCase):
    def args(self,root):
        return ['--run','--date','20010101','--root',str(root),'--config','synthetic','--reference','synthetic']

    def test_only_budget_exit_can_continue_and_the_total_new_window_budget_shrinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            processes=[]
            def create(command,**kwargs):
                child=Mock(pid=100+len(processes))
                def wait(**unused):
                    (Path(tmp)/'job-status.json').write_text(json.dumps(dict(running=False,pid=child.pid,
                        status='PARTIAL',reason='DRIVER_TIME_BUDGET')))
                    return 2
                child.wait.side_effect=wait;processes.append(command)
                if len(processes)==2:child.wait.return_value=0;child.wait.side_effect=None
                return child
            with patch.object(job,'cursor',side_effect=[0,0,720]),patch.object(job.subprocess,'Popen',side_effect=create),redirect_stdout(io.StringIO()):
                self.assertEqual(job.main(self.args(tmp)),0)
            self.assertEqual(len(processes),2)
            self.assertEqual(processes[1][processes[1].index('--max-clips')+1],'12')
            self.assertEqual(processes[1][processes[1].index('--max-batches')+1],'23')

    def test_auth_source_errors_and_another_pid_are_not_retried(self):
        for reason,pid in [('REAUTH_REQUIRED',100),('LENS_UNVERIFIED',100),('DRIVER_TIME_BUDGET',101)]:
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp)/'job-status.json').write_text(json.dumps(dict(running=False,pid=pid,status='PARTIAL',reason=reason)))
                child=Mock(pid=100);child.wait.return_value=2
                with patch.object(job,'cursor',return_value=0),patch.object(job.subprocess,'Popen',return_value=child) as popen,redirect_stdout(io.StringIO()):
                    self.assertEqual(job.main(self.args(tmp)),2)
                    self.assertEqual(popen.call_count,1)

    def test_timeout_terminates_only_owned_child_and_does_not_restart(self):
        child=Mock(pid=100);child.poll.return_value=None
        child.wait.side_effect=[job.subprocess.TimeoutExpired('synthetic',1),130]
        with tempfile.TemporaryDirectory() as tmp,patch.object(job,'cursor',return_value=0), \
             patch.object(job.subprocess,'Popen',return_value=child) as popen,redirect_stdout(io.StringIO()):
            self.assertEqual(job.main(self.args(tmp)),130)
            child.terminate.assert_called_once();self.assertEqual(popen.call_count,1)

    def test_only_clean_stop_at_owned_cycle_deadline_may_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Mock(pid=100);first.poll.return_value=None
            def wait(**kwargs):
                if kwargs['timeout']!=30:raise job.subprocess.TimeoutExpired('synthetic',1)
                (Path(tmp)/'job-status.json').write_text(json.dumps(dict(running=False,pid=100,
                    status='INTERRUPTED',reason='CHECKPOINT_RETAINED')))
                return 130
            first.wait.side_effect=wait
            second=Mock(pid=101);second.wait.return_value=0
            with patch.object(job,'cursor',side_effect=[0,0,8]),patch.object(job.subprocess,'Popen',side_effect=[first,second]) as popen,redirect_stdout(io.StringIO()):
                self.assertEqual(job.main(self.args(tmp)),0)
                self.assertEqual(popen.call_count,2);first.terminate.assert_called_once()

    def test_cursor_rollback_stops_before_starting_another_process(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(job,'cursor',side_effect=[5,4]), \
             patch.object(job.subprocess,'Popen') as popen,redirect_stdout(io.StringIO()):
            self.assertEqual(job.main(self.args(tmp)),2);popen.assert_not_called()


if __name__=='__main__':unittest.main()
