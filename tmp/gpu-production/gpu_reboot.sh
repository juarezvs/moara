set -eu
echo 'before_reboot_boot_id:'
cat /proc/sys/kernel/random/boot_id
systemctl is-enabled moara-gpu.service moara-gpu-warm.timer docker.service
systemctl reboot
