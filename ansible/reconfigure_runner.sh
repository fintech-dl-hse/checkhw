sudo -u bash -c 'cd /data/var/actions-runner && ./config.sh remove --local'
sudo systemctl restart 'actions.runner.fintech-dl-hse.ansible-runner_dtarasov@*.service'
sudo systemctl status 'actions.runner.fintech-dl-hse.ansible-runner_dtarasov@*.service'
