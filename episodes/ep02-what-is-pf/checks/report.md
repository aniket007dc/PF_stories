# Check report · ep02-what-is-pf

Checked commit `8408af3` on 2026-11-14 16:26 UTC. GitHub writes a new report after every upload.

**RESULT: POSTED** · This reel is live: https://www.instagram.com/reel/DfsSecYvJW2/ (posted 2026-11-14). Never post it again, and don't change its files: anything below is for a person.

## For a person

1. **Rule · pf_meaning** · rule 'pf_meaning' needs a person to check the source. Scheme ke tahat PF post-retirement benefit hai; person Gazette mein scheme ke objective/coverage paras se confirm karein.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf pf_meaning --by NAME`. Muse never marks a rule checked.
2. **Fact · emp_rate** · fact 'emp_rate' needs a person to check the source. Para 18: employee 12% of wages; notified class of establishments 10%. Person Gazette mein para 18 khol kar rate aur 'wages' ki definition confirm karein.
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf emp_rate --by NAME`. Muse never marks a fact checked.
3. **Fact · er_rate** · fact 'er_rate' needs a person to check the source. Para 18: employer bhi 12% of wages. Person Gazette mein para 18 confirm karein.
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf er_rate --by NAME`. Muse never marks a fact checked.
4. **Fact · eps_share** · fact 'eps_share' needs a person to check the source. EPS 2026 para 4: employer ke 12% mein se 8.33% pension fund mein jata hai. Person Gazette mein para 4 confirm karein.
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf eps_share --by NAME`. Muse never marks a fact checked.
5. **Fact · wage_ceiling** · fact 'wage_ceiling' needs a person to check the source. Cabinet ne 16 September 2026 ko ceiling Rs 15,000 se Rs 25,000 karne ko approve kiya; 17 September 2026 se lagu (S.O. 5109(E)). Person PIB release aur gazette notification se date aur rakam confirm karein — purane pages abhi bhi Rs 15,000 dikhate hain.
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf wage_ceiling --by NAME`. Muse never marks a fact checked.
6. **Fact · interest_rate** · fact 'interest_rate' needs a person to check the source. Quote: 'CBT recommended 8.25% annual rate of interest to be credited on EPF accumulations in members' accounts for the financial year 2025-26.' Rate har saal declare hota hai; FY 2024-25 bhi 8.25% tha.
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf interest_rate --by NAME`. Muse never marks a fact checked.
7. **Rule · employer_not_deducted** · rule 'employer_not_deducted' needs a person to check the source. Para 21: employer contribution employer ki taraf se hai, member ki wages se deduct nahi hoti. Person Gazette mein para 21 confirm karein.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf employer_not_deducted --by NAME`. Muse never marks a rule checked.
8. **Fact · final_wait_months** · fact 'final_wait_months' needs a person to check the source. Gazette pp. 90-91: member eligible nahi 'unless the member has not been employed ... for a continuous period of not less than twelve months'. Ep01 mein bhi yahi fact use hua tha.
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf final_wait_months --by NAME`. Muse never marks a fact checked.
9. **Rule · passbook_portal** · rule 'passbook_portal' needs a person to check the source. Person member portal khol kar passbook link confirm karein.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep02-what-is-pf passbook_portal --by NAME`. Muse never marks a rule checked.
10. **Voice · S01** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: सैलरी आई, पीएफ कट गया। ये पैसा कहाँ गया? · heard: सैलरी आई, पीआफ कट गया, ये पैसा कहां गया?
11. **Voice · S02** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: घबराओ मत। ये बचा है। · heard: घब्राओ मत, ये बचा है।
12. **Voice · S05** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: एक: आप बारह प्रतिशत देते हो, बेसिक प्लस डीए पर। · heard: एक आप बारा प्रतिषत देते हो बेसिक प्लस्डिया पर। / 1. You give 12% on Basic Plus DA
13. **Voice · S06** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: दो: कंपनी भी बारह प्रतिशत देती है, आपकी सैलरी से नहीं। · heard: दो, कंपनी भी बारह प्रतिषद देती है, आपकी साल्री से नहीं.
14. **Voice · S08** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: मान लो, बेसिक प्लस डीए पच्चीस हज़ार रुपये है, यही सीलिंग है। · heard: मान लो बेसिक प्लस्डिये 25,000 रुपये है यही सीलिंग है
15. **Voice · S10** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: बेसिक बीस हज़ार रुपये हो तो, आप दो हज़ार चार सौ रुपये देते हो। · heard: बेसिक 20,000 रुप्ये हो तो आप 2400 रुप्ये देते हो।
16. **Voice · S12** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: सैलरी पच्चीस हज़ार रुपये से ज़्यादा? पीएफ सिर्फ़ पच्चीस हज़ार रुपये पर कटता है। · heard: सैलरी 25,000 रुप्ये से ज्यादा पीएफ सिर्फ 25,000 रुप्ये पर कटता है
17. **Voice · S13** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: एक हिस्सा पीएफ़ में, बाक़ी पेंशन में। · heard: एक हिसा पीआफ में, बाकी पेंशन में.
18. **Voice · S17** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: सैलरी स्लिप में देखो। पीएफ वाली लाइन में तीन हज़ार रुपये दिखेगा। · heard: सालरी स्लिप में देखो, पीआफ वाली लाइन में 3,000 रुपये दिखेगा.

## To look at (Muse, not blocking)

OCR can't read symbols, lone digits or handwriting. Look at these in the reel and say in your report that they're right.
- `→` (too short or only symbols; check by eye)
- `↘` (too short or only symbols; check by eye)

## Notes

- Script E3.4: S19: long sentence (11 words): Jiski pehli salary se PF kata, us dost ko abhi bhejo.
- Script E3.3: estimated length 70 s and the shot timeline 94 s differ by more than 5 s

## Passed

- Episode file: brief, data, script, shots and post
- Not a repeat: topic, hook, script and photos are this reel's own (TOPICS.md)
- Reel file: every word on screen comes from that shot's card text
- Voice: 11 of 20 lines say every number and word
- Reel: every card read back exactly, and the length, size and sound are right

