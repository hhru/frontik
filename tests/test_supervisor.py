# coding=utf-8

import signal
import unittest

from .instances import find_free_port, frontik_broken_app, FrontikTestInstance, run_supervisor_command


class TestSupervisor(unittest.TestCase):
    def test_start_no_action(self):
        process = run_supervisor_command('supervisor-testapp', 1234, '')
        _, stderr = process.communicate()

        self.assertIn('missing action', stderr)
        self.assertEqual(1, process.poll())

    def test_start_incorrect_action(self):
        process = run_supervisor_command('supervisor-testapp', 1234, 'wtf')
        _, stderr = process.communicate()

        self.assertIn('incorrect action', stderr)
        self.assertEqual(1, process.poll())

    def test_start_restart_stop_status(self):
        port = find_free_port()
        supervisor_script = 'supervisor-superapp'
        process = run_supervisor_command(supervisor_script, port, 'start')
        _, stderr = process.communicate()

        self.assertIn('start worker', stderr)
        self.assertIn('all workers are running', stderr)
        self.assertEqual(0, process.poll())

        # Double start

        process = run_supervisor_command(supervisor_script, port, 'start')
        _, stderr = process.communicate()

        self.assertIn('another worker already started on', stderr)
        self.assertEqual(0, process.poll())

        # Status — running

        process = run_supervisor_command(supervisor_script, port, 'status')
        _, stderr = process.communicate()

        self.assertIn('all workers are running', stderr)
        self.assertEqual(0, process.poll())

        # Restart

        process = run_supervisor_command(supervisor_script, port, 'restart')
        _, stderr = process.communicate()

        self.assertIn('some of the workers are running, trying to kill', stderr)
        self.assertIn('stopping worker', stderr)
        self.assertIn('start worker', stderr)
        self.assertIn('all workers are running', stderr)
        self.assertEqual(0, process.poll())

        # Stop

        process = run_supervisor_command(supervisor_script, port, 'stop')
        _, stderr = process.communicate()

        self.assertIn('some of the workers are running, trying to kill', stderr)
        self.assertIn('stopping worker', stderr)
        self.assertIn('all workers are stopped', stderr)
        self.assertEqual(0, process.poll())

        # Status — stopped

        process = run_supervisor_command(supervisor_script, port, 'status')
        _, stderr = process.communicate()

        self.assertIn('all workers are stopped', stderr)
        self.assertEqual(3, process.poll())

    def test_broken(self):
        self.assertRaises(AssertionError, frontik_broken_app.start)
