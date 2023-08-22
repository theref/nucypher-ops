import re
from ansible.plugins.callback import CallbackBase
from ansible import context as ansible_context
from ansible.module_utils.common.collections import ImmutableDict

ansible_context.CLIARGS = ImmutableDict(
    {
        'syntax': False,
        'start_at_task': None,
        'verbosity': 0,
        'become_method': 'sudo'
    }
)


class AnsiblePlayBookResultsCollector(CallbackBase):
    """

    """

    def __init__(self, sock, *args, return_results=None, filter_output=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.playbook_results = []
        self.sock = sock
        self.results = return_results
        self.filter_output = filter_output

    def v2_playbook_on_play_start(self, play):
        if self.filter_output is not None:
            return
        name = play.get_name().strip()
        msg = f"\nPLAY {'*' * 100}\n" if not name else f"\nPLAY [{name}] {'*' * 100}\n"
        self.send_save(msg)

    def v2_playbook_on_task_start(self, task, is_conditional):

        if self.filter_output is not None:
            return
        if task.get_name() == 'Gathering Facts':
            return

        msg = f"\nTASK [{task.get_name()}] {'*' * 100}\n"
        self.send_save(msg)

    def v2_runner_on_ok(self, result, *args, **kwargs):
        task_name = result._task.get_name()

        if self.filter_output is not None and task_name not in self.filter_output:
            return

        if self.filter_output is None:
            if result.is_changed():
                data = f'[{result._host.name}]=> changed'
            else:
                data = f'[{result._host.name}]=> ok'
            self.send_save(
                data, color='yellow' if result.is_changed() else 'green')
        if 'msg' in result._task_fields['args']:
            self.send_save('\n')
            msg = result._task_fields['args']['msg']
            self.send_save(msg, color='white',)
            if self.results:
                for k in self.results.keys():
                    regex = fr'{k}:\s*(?P<data>.*)'
                    if match := re.search(regex, msg, flags=re.MULTILINE):
                        self.results[k].append(
                            (result._host.name, match.groupdict()['data']))

    def v2_runner_on_failed(self, result, *args, **kwargs):
        if self.filter_output is not None:
            return
        if 'changed' in result._result:
            del result._result['changed']
        data = f'fail: [{result._host.name}]=> failed: {self._dump_results(result._result)}'
        self.send_save(data, color='red')

    def v2_runner_on_unreachable(self, result):
        if 'changed' in result._result:
            del result._result['changed']
        data = f'[{result._host.name}]=> unreachable: {self._dump_results(result._result)}'
        self.send_save(data)

    def v2_runner_on_skipped(self, result):
        if self.filter_output is not None:
            return
        if 'changed' in result._result:
            del result._result['changed']
        data = f'[{result._host.name}]=> skipped: {self._dump_results(result._result)}'
        self.send_save(data, color='blue')

    def v2_playbook_on_stats(self, stats):
        if self.filter_output is not None:
            return
        hosts = sorted(stats.processed.keys())
        data = f"\nPLAY RECAP {'*' * 100}\n"
        self.send_save(data)
        for h in hosts:
            s = stats.summarize(h)
            msg = f"{h} : ok={s['ok']} changed={s['changed']} unreachable={s['unreachable']} failed={s['failures']} skipped={s['skipped']}"
            self.send_save(msg)

    def send_save(self, data, color=None):
        self.sock.echo(data, color=color)
        self.playbook_results.append(data)
