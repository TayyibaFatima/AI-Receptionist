-- One-time update for databases seeded with the FIRST version of the demo data.
-- It renames the old "... Consultation" aesthetic services into real treatments (ids and bookings are kept).
-- Demo data only. Safe to run more than once.

UPDATE services SET name='Chemical Peel', price=9000, duration_minutes=45,
  description='A peeling treatment performed by the clinic team. Suitability is assessed by a doctor. (demo description)'
WHERE name='Chemical Peel Consultation' AND NOT EXISTS (SELECT 1 FROM services WHERE name='Chemical Peel');

UPDATE services SET name='Laser Hair Reduction', price=8000, duration_minutes=45,
  description='A laser treatment for reducing unwanted hair. (demo description)'
WHERE name='Laser Hair Reduction Consultation' AND NOT EXISTS (SELECT 1 FROM services WHERE name='Laser Hair Reduction');

UPDATE services SET name='Botox', price=25000, duration_minutes=30,
  description='A botulinum toxin treatment performed by an aesthetic physician. (demo description)'
WHERE name='Botox Consultation' AND NOT EXISTS (SELECT 1 FROM services WHERE name='Botox');

UPDATE services SET name='Dermal Filler', price=30000, duration_minutes=45,
  description='A dermal filler treatment performed by an aesthetic physician. (demo description)'
WHERE name='Dermal Filler Consultation' AND NOT EXISTS (SELECT 1 FROM services WHERE name='Dermal Filler');

UPDATE services SET name='Acne Treatment', price=8500, duration_minutes=45,
  description='A treatment session for acne-prone skin. A doctor consultation is recommended first. (demo description)'
WHERE name='Acne Consultation' AND NOT EXISTS (SELECT 1 FROM services WHERE name='Acne Treatment');

UPDATE services SET description='See a dermatologist about skin, hair or nail concerns, including acne. The doctor can advise whether a treatment is suitable. (demo description)'
WHERE name='Dermatologist Consultation';
