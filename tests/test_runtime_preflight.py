import unittest

from aki.runtime_preflight import RuntimePreflightError, assert_interpreter_mount_allows_exec


class RuntimeMountTests(unittest.TestCase):
    def setUp(self):
        self.mounts = ['overlay / overlay ro,relatime 0 0',
                       'tmpfs /env tmpfs rw,nosuid,nodev,noexec,uid=65534 0 0']

    def test_recorded_failure_is_rejected_before_venv_bootstrap(self):
        with self.assertRaisesRegex(RuntimePreflightError, 'noexec'):
            assert_interpreter_mount_allows_exec('/env/bin/python3', self.mounts)

    def test_base_interpreter_does_not_require_executable_tmpfs(self):
        self.assertEqual('/', assert_interpreter_mount_allows_exec('/usr/local/bin/python3', self.mounts))
        self.assertEqual('/', assert_interpreter_mount_allows_exec('/environment/python3', self.mounts))

    def test_nested_mount_is_decisive(self):
        self.mounts.append('tmpfs /env/bin tmpfs ro,nodev,nosuid 0 0')
        self.assertEqual('/env/bin', assert_interpreter_mount_allows_exec('/env/bin/python3', self.mounts))

    def test_missing_or_ambiguous_path_fails_closed(self):
        for path, records in [('/env/python', []), ('env/python', self.mounts),
                              ('/env/../python', self.mounts), ('/env/python', ['bad'])]:
            with self.subTest(path=path, records=records):
                with self.assertRaises(RuntimePreflightError):
                    assert_interpreter_mount_allows_exec(path, records)


if __name__ == '__main__':
    unittest.main()
