# systemd units for the TH-D75 tools

## Bluetooth SPP binding

`thd75-bt-bind.service.example` recreates `/dev/rfcomm0` at boot after the
TH-D75 has been paired and trusted.

```bash
sudo install -m 0755 infra/systemd/thd75-bt-bind.sh /usr/local/sbin/thd75-bt-bind
sudo cp infra/systemd/thd75-bt-bind.service.example \
  /etc/systemd/system/thd75-bt-bind.service
sudoedit /etc/systemd/system/thd75-bt-bind.service
# set THD75_BT_MAC and THD75_BT_OWNER
sudo systemctl daemon-reload
sudo systemctl enable --now thd75-bt-bind.service
systemctl status thd75-bt-bind.service
rfcomm -a
```

The unit releases a stale bind, binds SPP channel 2, and gives `/dev/rfcomm0`
to the desktop user. If the radio is off at boot, start the unit manually:

```bash
sudo systemctl restart thd75-bt-bind.service
```

The settings UI and `d75mon` auto-fallback still prefer USB when present.
