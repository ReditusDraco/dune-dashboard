"""Tests for the battlegroup update guard (block while game pods run)."""

from app.services.k8s import K8sService

NS = 'funcom-seabass-sh-b17a5f036d1f7882-ccdijf'


class FakeSSH:
    def __init__(self, out='', rc=0):
        self.out = out
        self.rc = rc
        self.commands = []

    def run(self, command, timeout=30):
        self.commands.append(command)
        return self.out, '', self.rc


def make_k8s(out='', rc=0):
    return K8sService(ssh_service=FakeSSH(out, rc), namespace=NS)


class TestRunningGamePods:
    def test_detects_running_game_pods(self):
        out = (
            f'sh-b17a5f036d1f7882-ccdijf-sg-overmap-pod-2   Running\n'
            f'sh-b17a5f036d1f7882-ccdijf-sg-survival-1-pod-1   Running\n'
            f'sh-b17a5f036d1f7882-ccdijf-bgd-deploy-xxx   Running\n'
            f'sh-b17a5f036d1f7882-ccdijf-mq-game-sts-0   Running\n'
        )
        running = make_k8s(out).get_running_game_pods()
        # Only sg-*-pod-* count as game servers; infra pods do not block.
        assert running == [
            'sh-b17a5f036d1f7882-ccdijf-sg-overmap-pod-2',
            'sh-b17a5f036d1f7882-ccdijf-sg-survival-1-pod-1',
        ]

    def test_empty_when_no_game_pods_running(self):
        out = (
            f'sh-b17a5f036d1f7882-ccdijf-bgd-deploy-xxx   Running\n'
            f'sh-b17a5f036d1f7882-ccdijf-sg-overmap-pod-2   Completed\n'
            f'sh-b17a5f036d1f7882-ccdijf-mq-game-sts-0   Running\n'
        )
        assert make_k8s(out).get_running_game_pods() == []

    def test_empty_when_no_pods(self):
        assert make_k8s('').get_running_game_pods() == []

    def test_none_when_status_unknown(self):
        assert make_k8s('', rc=1).get_running_game_pods() is None
