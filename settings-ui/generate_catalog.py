#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build catalog.json for the TH-D75 settings UI from local research data."""
import argparse
import csv
import json
import os
import re
import sys

ap = argparse.ArgumentParser(description="Build catalog.json for the TH-D75 settings UI.")
ap.add_argument("--schema", required=True, help="MCP-D75 menu schema JSON")
ap.add_argument("--menu-map", required=True, help="menu-map.tsv")
ap.add_argument("--menu-rows", required=True, help="menu-rows.tsv")
ap.add_argument("--swift-index", default="", help="optional THD75MenuNumberIndex.swift")
ap.add_argument("--out", required=True, help="output catalog.json")
args = ap.parse_args()

SCHEMA = args.schema
MENU_MAP = args.menu_map
ROW_MAP = args.menu_rows
OUT = args.out

schema=json.load(open(SCHEMA))
# offset_hex -> menu number string, and setting_id -> firmware label
menu_by_offset={}
label_by_id={}
with open(MENU_MAP) as fh:
    for row in csv.DictReader(fh, delimiter='\t'):
        off=row['offset_hex'].lower()
        m=row.get('menu_numbers','').strip().split()
        if m: menu_by_offset.setdefault(off, m[0])
with open(ROW_MAP) as fh:
    for row in csv.DictReader(fh, delimiter='\t'):
        sid=row.get('setting_id','').strip()
        lab=row.get('firmware_labels','').strip()
        if sid and lab and row.get('status')=='mapped':
            label_by_id[sid]=lab.split(' | ')[0]

# Official menu numbers from the upstream generator index.
SWIFT=args.swift_index
swift_text=open(SWIFT).read() if os.path.exists(SWIFT) else ''
id2menus={}
for m in re.finditer(r'if settingID\.hasPrefix\("([^"]+)"\)\s*\{\s*return\s*\[([^\]]*)\]', swift_text):
    id2menus['prefix:'+m.group(1)]=re.findall(r'"([^"]+)"', m.group(2))
for m in re.finditer(r'case\s+([^:]+):\s*return\s*\[([^\]]*)\]', swift_text):
    nums=re.findall(r'"([^"]+)"', m.group(2))
    for i in re.findall(r'"([^"]+)"', m.group(1)):
        id2menus[i]=nums

def official_menu(sid):
    if sid in id2menus: return id2menus[sid][0] if id2menus[sid] else ''
    for k,v in id2menus.items():
        if k.startswith('prefix:') and sid.startswith(k[7:]) and v: return v[0]
    return ''

def split_name(name):
    s=re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
    s=re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    for a,b in [('Eq','EQ'),('Lcd','LCD'),('Usb','USB'),('Pf','PF'),('Vox','VOX'),
                ('Tnc','TNC'),('Dv','DV'),('Gps','GPS'),('Aprs','APRS'),('Rx','RX'),
                ('Tx','TX'),('Cw','CW'),('Ssb','SSB'),('Am','AM'),('Fm','FM'),
                ('Dtmf','DTMF'),('Emr','EMR'),('Nmea','NMEA'),('Qso','QSO')]:
        s=re.sub(r'\b'+a+r'\b', b, s)
    s=re.sub(r'(?<=[A-Za-z])(\d+)$', r' \1', s)
    s=s.replace('Poweron','Power-on').replace('On Off','On/Off')
    return s

def category_for(mid, menu):
    if menu:
        try: n=int(menu,16)
        except ValueError: n=None
        if n is not None:
            if 0x900<=n<=0x907: return 'display'
            if 0x910<=n<=0x919: return 'audio'
            if 0x930<=n<=0x936: return 'bluetooth'
            if 0x980<=n<=0x985: return 'interfaces'
            if 0x400<=n<=0x4FF: return 'gps'
            if 0x500<=n<=0x5FF: return 'aprs'
            if 0x600<=n<=0x6FF: return 'dv'
            if 0x100<=n<=0x3FF or 0x700<=n<=0x8FF or 0x920<=n<=0x929 or 0x940<=n<=0x97F or 0x986<=n<=0x9FF: return 'radio'
    if mid.startswith('gps.'): return 'gps'
    if mid.startswith('aprs.'): return 'aprs'
    if mid.startswith('dv.'): return 'dv'
    return 'other'

HIGH_RISK={
 'radio.TxInhibit','radio.UsbFunction','radio.BluetoothOnOff','radio.BluetoothAutoConnect',
 'radio.DvGatewayInterface','radio.KissModeInterface','radio.DigitalModeInterface',
 'radio.PcOutputGps','radio.PcOutputAprs','radio.PowerOnMessage',
 'dv.DvGatewayModeDvGateway','dv.AutoReplyTimingTxRx','dv.DataTxEndTimingTxRx',
 'aprs.TncMode','aprs.BeaconTxMethod','radio.TxMonitor'
}

def codec_info(op):
    c=op.get('codec') or {}
    kind=c.get('kind'); dom=op.get('domain') or {}
    if kind in ('bool',): return dict(kind='bool', type='toggle')
    if kind=='bit_field' and c.get('width',1)==1: return dict(kind='bit', type='toggle', bit=c.get('bit',0), width=1)
    if kind=='byte':
        if c.get('value_type')=='enum' and c.get('enum_type'):
            return dict(kind='byte', type='select', enum_type=c['enum_type'])
        if dom.get('kind')=='range':
            return dict(kind='byte', type='number', min=dom.get('min',0), max=dom.get('max',255), step=dom.get('step',1))
        if dom.get('kind')=='choices':
            return dict(kind='byte', type='number', min=min(dom.get('allowed_values') or [0]), max=max(dom.get('allowed_values') or [255]), step=1, allowed_values=dom.get('allowed_values') or [])
        return dict(kind='byte', type='number', min=0, max=255, step=1)
    if kind=='unsigned_le':
        return dict(kind='unsigned_le', type='number', width=c.get('width',2), min=dom.get('min',0), max=dom.get('max',65535), step=dom.get('step',1))
    if kind=='fixed_string':
        return dict(kind='fixed_string', type='text', length=c.get('length',16), encoding=c.get('encoding','utf8'))
    return None

def enum_map(menu):
    out={}
    for e in menu.get('enum_types') or []:
        out[e.get('name')] = [(o.get('value'), o.get('label') or o.get('resource_key') or str(o.get('value'))) for o in e.get('options',[])]
    return out

items=[]
seen=set()
for menu in schema['menus']:
    emaps=enum_map(menu)
    for op in menu['operations']:
        if op.get('role')!='field': continue
        name=op.get('name'); off=op.get('offset')
        if not name or off is None: continue
        if op.get('category')=='blob' or op.get('writable') is False: continue
        if (op.get('address') or {}).get('terms'): continue
        if off >= 500000: continue
        info=codec_info(op)
        if not info: continue
        mid=f"{menu['menu']}.{name}"
        if mid in seen: continue
        option_list=None
        if info['type']=='select':
            raw=emaps.get(info['enum_type'])
            if not raw: continue
            option_list=[[v,lab] for v,lab in raw]
            default=option_list[0][0] if option_list else 0
        elif info['type']=='toggle':
            default=False
        elif info['type']=='number':
            default=info.get('min',0)
        else:
            default=''
        menu_no=official_menu(mid) or menu_by_offset.get(hex(off).lower(), menu_by_offset.get(op.get('offset_hex','').lower(), ''))
        label=label_by_id.get(mid) or split_name(name)
        item={
            'id':mid,'label':label,'category':category_for(mid,menu_no),
            'description':"",
            'type':info['type'],'value':default,
            'menu':menu_no,'offset':f"0x{off:05X}",
            'keywords':f"{name} {mid} {menu_no} {label}",
            'risk':'high' if mid in HIGH_RISK else 'normal',
            'meta':info,
        }
        if option_list is not None:
            item['options']=option_list
            item['value']=default
        if info['type']=='number':
            for k in ('min','max','step'):
                if k in info: item[k]=info[k]
            if info.get('allowed_values'): item['allowed_values']=info['allowed_values']
        if info['type']=='text':
            item['maxlength']=info.get('length')
        items.append(item); seen.add(mid)

# deterministic ordering by category then label
order={'display':0,'audio':1,'radio':2,'gps':3,'aprs':4,'dv':5,'bluetooth':6,'interfaces':7,'other':8}
items.sort(key=lambda x:(order.get(x['category'],99), x['label'].lower()))
json.dump({'generated':'2026-11-22','schema_version':schema.get('schema_version'),'settings':items}, open(OUT,'w'), indent=1)
from collections import Counter
print('wrote',OUT,len(items),'settings')
print(Counter(i['category'] for i in items))
print(Counter(i['type'] for i in items))
print(Counter(i['risk'] for i in items))
