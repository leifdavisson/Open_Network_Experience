import subprocess
import os
import tempfile
import pytest

# Create a robust mock environment that sets up our dummy dependencies
@pytest.fixture
def mock_env():
    with tempfile.TemporaryDirectory() as temp_dir:
        bin_dir = os.path.join(temp_dir, 'bin')
        os.makedirs(bin_dir)

        # We will mock the following commands
        commands = ['ssh', 'scp', 'sshpass', 'stat']
        for cmd in commands:
            cmd_path = os.path.join(bin_dir, cmd)
            with open(cmd_path, 'w') as f:
                f.write("#!/usr/bin/env bash\n")
                if cmd == 'stat':
                    f.write("echo 600\n")
                elif cmd == 'sshpass':
                    f.write('eval "${@: -1}"\n')
                else:
                    f.write("echo 'Mocked {}'\n".format(cmd))
            os.chmod(cmd_path, 0o755)

        # Path setup
        env = os.environ.copy()
        env['PATH'] = f"{bin_dir}:{env.get('PATH', '')}"

        yield env

def create_dummy_credentials_file(tmp_path, perms=0o600):
    cred_file = tmp_path / "creds.txt"
    cred_file.write_text("SSH_PASS=testpass\n")
    cred_file.chmod(perms)
    return cred_file

def test_missing_arguments():
    # Should exit with code 1 if missing arguments
    result = subprocess.run(['./scripts/offboard.sh'], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Missing required arguments" in result.stderr

def test_invalid_device_ip():
    result = subprocess.run(['./scripts/offboard.sh', 'invalid-ip', 'user', 'creds.txt'], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Invalid DEVICE_IP format" in result.stderr

def test_invalid_username():
    result = subprocess.run(['./scripts/offboard.sh', '127.0.0.1', 'user name', 'creds.txt'], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Invalid USERNAME format" in result.stderr

def test_missing_credentials_file():
    result = subprocess.run(['./scripts/offboard.sh', '127.0.0.1', 'user', 'missing.txt'], capture_output=True, text=True)
    assert result.returncode == 1
    assert "does not exist" in result.stderr

def test_insecure_credentials_file(mock_env, tmp_path):
    # Set up our mocked bin dir to return insecure permissions for stat
    bin_dir = mock_env['PATH'].split(':')[0]
    stat_mock = os.path.join(bin_dir, 'stat')
    with open(stat_mock, 'w') as f:
        f.write("#!/usr/bin/env bash\necho 644\n")

    cred_file = create_dummy_credentials_file(tmp_path, 0o644)
    result = subprocess.run(['./scripts/offboard.sh', '127.0.0.1', 'user', str(cred_file)], env=mock_env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Security Error: Insecure permissions" in result.stderr

def test_unknown_mode(mock_env, tmp_path):
    cred_file = create_dummy_credentials_file(tmp_path)
    result = subprocess.run(['./scripts/offboard.sh', '127.0.0.1', 'user', str(cred_file), '--unknown'], env=mock_env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Unknown mode" in result.stderr

def test_successful_wipe(mock_env, tmp_path):
    cred_file = create_dummy_credentials_file(tmp_path)
    # The script uses grep to check active services/containers in post-audit.
    # Our simple SSH mock returns "Mocked ssh" which might cause grep to fail, producing warnings.
    # We will adjust the mock SSH specifically to return output that avoids grep matches for audit.
    bin_dir = mock_env['PATH'].split(':')[0]
    ssh_mock = os.path.join(bin_dir, 'ssh')
    with open(ssh_mock, 'w') as f:
        f.write("#!/usr/bin/env bash\n")
        f.write('if [[ "$*" == *"hostname"* ]]; then echo "testhost"; exit 0; fi\n')
        f.write('if [[ "$*" == *"cat /etc/sensor/reconciler.json"* ]]; then echo "testuuid"; exit 0; fi\n')
        f.write('if [[ "$*" == *"SSH_OK"* ]]; then echo "SSH_OK"; exit 0; fi\n')
        # Audit checks should produce empty output to pass
        f.write('if [[ "$*" == *"systemctl is-active"* ]]; then echo "inactive"; exit 0; fi\n')
        f.write('if [[ "$*" == *"ls -d /usr/local/bin/reconciler.py"* ]]; then exit 0; fi\n')
        f.write('if [[ "$*" == *"docker ps -q"* ]]; then exit 0; fi\n')
        f.write('exit 0\n')

    result = subprocess.run(['./scripts/offboard.sh', '127.0.0.1', 'user', str(cred_file), '--wipe'], env=mock_env, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Offboarding Complete" in result.stdout

def test_successful_archive(mock_env, tmp_path):
    cred_file = create_dummy_credentials_file(tmp_path)

    bin_dir = mock_env['PATH'].split(':')[0]
    ssh_mock = os.path.join(bin_dir, 'ssh')
    with open(ssh_mock, 'w') as f:
        f.write("#!/usr/bin/env bash\n")
        f.write('if [[ "$*" == *"hostname"* ]]; then echo "testhost"; exit 0; fi\n')
        f.write('if [[ "$*" == *"cat /etc/sensor/reconciler.json"* ]]; then echo "testuuid"; exit 0; fi\n')
        f.write('if [[ "$*" == *"SSH_OK"* ]]; then echo "SSH_OK"; exit 0; fi\n')
        f.write('if [[ "$*" == *"systemctl is-active"* ]]; then echo "inactive"; exit 0; fi\n')
        f.write('if [[ "$*" == *"ls -d /usr/local/bin/reconciler.py"* ]]; then exit 0; fi\n')
        f.write('if [[ "$*" == *"docker ps -q"* ]]; then exit 0; fi\n')
        f.write('exit 0\n')

    scp_mock = os.path.join(bin_dir, 'scp')
    with open(scp_mock, 'w') as f:
        f.write("#!/usr/bin/env bash\n")
        # Touch the destination file so sha256sum works
        f.write('mkdir -p $(dirname "${@: -1}")\n')
        f.write('touch "${@: -1}"\n')
        f.write('echo "Mocked scp"\n')

    result = subprocess.run(['./scripts/offboard.sh', '127.0.0.1', 'user', str(cred_file), '--archive'], env=mock_env, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Creating Compressed Pre-Wipe State Archive" in result.stdout
    assert "Offboarding Complete" in result.stdout
