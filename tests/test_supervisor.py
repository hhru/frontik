# coding=utf-8

import unittest

from .instances import find_free_port, frontik_broken_app, run_supervisor_command


class TestSupervisor(unittest.TestCase):
    def test_start_no_action(self):
        process = run_supervisor_command('supervisor-testapp', 1234, '')
        _, stderr = process.communicate()

        self.assertIn(b'missing action', stderr)
        self.assertEqual(1, process.poll())

    def test_start_incorrect_action(self):
        process = run_supervisor_command('supervisor-testapp', 1234, 'wtf')
        _, stderr = process.communicate()

        self.assertIn(b'incorrect action', stderr)
        self.assertEqual(1, process.poll())

    def test_start_restart_stop_status(self):
        port = find_free_port()
        supervisor_script = 'supervisor-superapp'
        process = run_supervisor_command(supervisor_script, port, 'start')
        _, stderr = process.communicate()

        self.assertIn(b'start worker', stderr)
        self.assertIn(b'all workers are running', stderr)
        self.assertEqual(0, process.poll())

        # Double start

        process = run_supervisor_command(supervisor_script, port, 'start')
        _, stderr = process.communicate()

        self.assertIn(b'another worker already started on', stderr)
        self.assertEqual(0, process.poll())

        # Status — running

        process = run_supervisor_command(supervisor_script, port, 'status')
        _, stderr = process.communicate()

        self.assertIn(b'all workers are running', stderr)
        self.assertEqual(0, process.poll())

        # Restart

        process = run_supervisor_command(supervisor_script, port, 'restart')
        _, stderr = process.communicate()

        self.assertIn(b'some of the workers are running, trying to kill', stderr)
        self.assertIn(b'stopping worker', stderr)
        self.assertIn(b'start worker', stderr)
        self.assertIn(b'all workers are running', stderr)
        self.assertEqual(0, process.poll())

        # Stop

        process = run_supervisor_command(supervisor_script, port, 'stop')
        _, stderr = process.communicate()

        self.assertIn(b'some of the workers are running, trying to kill', stderr)
        self.assertIn(b'stopping worker', stderr)
        self.assertIn(b'all workers are stopped', stderr)
        self.assertEqual(0, process.poll())

        # Status — stopped

        process = run_supervisor_command(supervisor_script, port, 'status')
        _, stderr = process.communicate()

        self.assertIn(b'all workers are stopped', stderr)
        self.assertEqual(3, process.poll())

    def test_broken(self):
        self.assertRaises(AssertionError, frontik_broken_app.start)
