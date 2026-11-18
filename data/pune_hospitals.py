"""Public facts checked against official sources on 2026-11-18.
No hospital partnership, live inventory, fleet availability or ETA is asserted.
The check date is fixed at research time; startup does not re-verify contacts.
"""
from datetime import datetime

CHECKED_AT = datetime(2026, 11, 18, 16, 0)
HOSPITALS = [
    dict(slug='jehangir', name='Jehangir Hospital', city='Pune', area='Sassoon Road', hospital_type='private',
         address='32, Sassoon Road, Pune 411001, Maharashtra', phone='+912066819966',
         source_url='https://www.jehangirhospital.com/emergency-and-trauma-care/ambulance-services/',
         ambulance_phone='+918888881066', ambulance_alternate=None, contact_label='Emergency & ambulance desk'),
    dict(slug='ruby-hall', name='Ruby Hall Clinic — Sassoon Road', city='Pune', area='Sassoon Road', hospital_type='private',
         address='40, Sassoon Road, Pune 411001, Maharashtra', phone='+912066455100',
         source_url='https://rubyhall.com/contact-us/',
         ambulance_source='https://rubyhall.com/broad-specialities/accident-emergency/',
         ambulance_phone='+917057700700', ambulance_alternate='+912066455676', contact_label='Emergency ambulance dispatch'),
    dict(slug='kem-pune', name='KEM Hospital, Pune', city='Pune', area='Rasta Peth', hospital_type='private',
         address='489, Rasta Peth, Sardar Moodliar Road, Pune 411011, Maharashtra', phone='+912026217300',
         source_url='https://www.kemhospitalpune.org/contact-us/',
         ambulance_phone='+919421018970', ambulance_alternate='+919850918420', contact_label='Ambulance desk'),
    dict(slug='deenanath-mangeshkar', name='Deenanath Mangeshkar Hospital & Research Center', city='Pune', area='Erandwane', hospital_type='private',
         address='Near Mhatre Bridge, Erandwane, Pune 411004, Maharashtra', phone='+912040151000',
         source_url='https://www.dmhospital.org/contact-us',
         ambulance_phone='+912040151540', ambulance_alternate=None, contact_label='Ambulance desk'),
    dict(slug='poona-hospital', name='Poona Hospital & Research Centre', city='Pune', area='Sadashiv Peth', hospital_type='private',
         address='27, Sadashiv Peth, near Alka Talkies, Pune 411030, Maharashtra', phone='+912066096000',
         source_url='https://poonahospital.org/contact-us/',
         ambulance_source='https://poonahospital.org/registration-admission/',
         ambulance_phone='+912066096000', ambulance_alternate=None, contact_label='Emergency & ambulance desk'),
    dict(slug='sassoon-general', name='Sassoon General Hospital', city='Pune', area='Pune Station', hospital_type='government',
         address='J. P. Narayan Road, near Pune Railway Station, Pune 411001, Maharashtra', phone='+912026128000',
         source_url='https://bjgmcpune.com/wp-content/uploads/2025/02/Part-A-NMC.pdf',
         ambulance_phone=None, ambulance_alternate=None, contact_label=None),
]
