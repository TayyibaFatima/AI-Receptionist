-- =====================================================================
-- DEMONSTRATION DATA ONLY - NOT real clinic information.
-- Doctors, fees, prices, durations and schedules below are invented samples.
-- Replace them with your clinic's real data before real use.
-- Safe to run more than once (it skips rows that already exist).
-- =====================================================================

INSERT INTO clinic_info (id, clinic_name, address, phone, email, opening_hours, general_info, currency)
VALUES (1, 'Luméra Aesthetics',
        'DEMO ADDRESS: 12 Sample Street, Karachi',
        '+92 300 0000000 (demo)',
        'hello@example.com (demo)',
        'Monday to Saturday, 9:00 AM - 7:00 PM. Closed on Sunday. (demo hours)',
        'Luméra Aesthetics offers aesthetic treatments and general doctor consultations. NOTE: this installation currently contains sample demonstration data.',
        'PKR')
ON CONFLICT (id) DO NOTHING;

INSERT INTO services (name, category, description, price, duration_minutes) VALUES
 ('HydraFacial', 'aesthetic_treatment', 'A multi-step facial treatment that cleanses and hydrates the skin. (demo description)', 12000, 60),
 ('Chemical Peel', 'aesthetic_treatment', 'A peeling treatment performed by the clinic team. Suitability is assessed by a doctor. (demo description)', 9000, 45),
 ('Laser Hair Reduction', 'aesthetic_treatment', 'A laser treatment for reducing unwanted hair. (demo description)', 8000, 45),
 ('Botox', 'aesthetic_treatment', 'A botulinum toxin treatment performed by an aesthetic physician. (demo description)', 25000, 30),
 ('Dermal Filler', 'aesthetic_treatment', 'A dermal filler treatment performed by an aesthetic physician. (demo description)', 30000, 45),
 ('Acne Treatment', 'aesthetic_treatment', 'A treatment session for acne-prone skin. A doctor consultation is recommended first. (demo description)', 8500, 45),
 ('General Physician Consultation', 'general_consultation', 'A general check-up and consultation with a physician. (demo description)', 2500, 30),
 ('Dermatologist Consultation', 'general_consultation', 'See a dermatologist about skin, hair or nail concerns, including acne. The doctor can advise whether a treatment is suitable. (demo description)', 4000, 30),
 ('Specialist Consultation', 'general_consultation', 'A consultation with a visiting medical specialist. (demo description)', 5000, 30)
ON CONFLICT (name) DO NOTHING;

INSERT INTO doctors (full_name, specialization, profile_description, consultation_fee)
SELECT v.full_name, v.specialization, v.profile_description, v.fee
FROM (VALUES
 ('Dr. Amna (Demo)',   'General Physician',  'DEMO PROFILE: sample general physician. Replace with real doctor information.', 2500),
 ('Dr. Bilal (Demo)',  'Dermatologist',      'DEMO PROFILE: sample dermatologist. Replace with real doctor information.', 4000),
 ('Dr. Hira (Demo)',   'Aesthetic Physician','DEMO PROFILE: sample aesthetic physician. Replace with real doctor information.', 5000),
 ('Dr. Kamran (Demo)', 'Internal Medicine Specialist', 'DEMO PROFILE: sample visiting specialist. Replace with real doctor information.', 5000)
) AS v(full_name, specialization, profile_description, fee)
WHERE NOT EXISTS (SELECT 1 FROM doctors d WHERE d.full_name = v.full_name);

-- Which doctor performs which service
INSERT INTO doctor_services (doctor_id, service_id)
SELECT d.id, s.id
FROM (VALUES
 ('Dr. Amna (Demo)',   'General Physician Consultation'),
 ('Dr. Bilal (Demo)',  'Dermatologist Consultation'),
 ('Dr. Bilal (Demo)',  'Acne Treatment'),
 ('Dr. Bilal (Demo)',  'Chemical Peel'),
 ('Dr. Bilal (Demo)',  'Laser Hair Reduction'),
 ('Dr. Hira (Demo)',   'HydraFacial'),
 ('Dr. Hira (Demo)',   'Chemical Peel'),
 ('Dr. Hira (Demo)',   'Laser Hair Reduction'),
 ('Dr. Hira (Demo)',   'Botox'),
 ('Dr. Hira (Demo)',   'Dermal Filler'),
 ('Dr. Hira (Demo)',   'Acne Treatment'),
 ('Dr. Kamran (Demo)', 'Specialist Consultation')
) AS m(doctor_name, service_name)
JOIN doctors d ON d.full_name = m.doctor_name
JOIN services s ON s.name = m.service_name
ON CONFLICT DO NOTHING;

-- Weekly schedules (day_of_week: 0 = Monday ... 5 = Saturday)
INSERT INTO doctor_schedules (doctor_id, day_of_week, start_time, end_time, slot_minutes)
SELECT d.id, v.dow, v.start_time::time, v.end_time::time, v.slot
FROM (VALUES
 ('Dr. Amna (Demo)', 0, '09:00', '13:00', 30), ('Dr. Amna (Demo)', 1, '09:00', '13:00', 30),
 ('Dr. Amna (Demo)', 2, '09:00', '13:00', 30), ('Dr. Amna (Demo)', 3, '09:00', '13:00', 30),
 ('Dr. Amna (Demo)', 4, '09:00', '13:00', 30),
 ('Dr. Bilal (Demo)', 0, '14:00', '19:00', 30), ('Dr. Bilal (Demo)', 2, '14:00', '19:00', 30),
 ('Dr. Bilal (Demo)', 4, '14:00', '19:00', 30), ('Dr. Bilal (Demo)', 1, '10:00', '14:00', 30),
 ('Dr. Bilal (Demo)', 3, '10:00', '14:00', 30), ('Dr. Bilal (Demo)', 5, '10:00', '14:00', 30),
 ('Dr. Hira (Demo)', 0, '11:00', '18:00', 30), ('Dr. Hira (Demo)', 1, '11:00', '18:00', 30),
 ('Dr. Hira (Demo)', 2, '11:00', '18:00', 30), ('Dr. Hira (Demo)', 3, '11:00', '18:00', 30),
 ('Dr. Hira (Demo)', 4, '11:00', '18:00', 30), ('Dr. Hira (Demo)', 5, '11:00', '18:00', 30),
 ('Dr. Kamran (Demo)', 1, '15:00', '19:00', 30), ('Dr. Kamran (Demo)', 3, '15:00', '19:00', 30)
) AS v(doctor_name, dow, start_time, end_time, slot)
JOIN doctors d ON d.full_name = v.doctor_name
ON CONFLICT DO NOTHING;
