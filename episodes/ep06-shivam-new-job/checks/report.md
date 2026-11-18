# Check report · ep06-shivam-new-job

Checked commit `fa6a3ed` on 2026-11-18 17:15 UTC. GitHub writes a new report after every upload.

**RESULT: WAITING** · Nothing for Muse to fix. A person's part is left (below).

## For a person

1. **Rule · uan_for_life** · rule 'uan_for_life' needs a person to check the source. Find the answer saying the UAN 'remains valid throughout the life of a member and does not change with the change of employment', and that a member doesn't need to obtain a UAN again on a job change. The research couldn't open these pages on 18 November 2026 (EPFO's and PIB's sites refused automated reading); the wording above is from search results only, so open each one and confirm it.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job uan_for_life --by NAME`. Muse never marks a rule checked.
2. **Rule · declare_uan_on_joining** · rule 'declare_uan_on_joining' needs a person to check the source. Find: a member declares the UAN to later employers in Form-11 (the Declaration Form), and the employer links the new member ID with the existing UAN. The PIB release (https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=143612) asks establishments to take from a new joiner any UAN allotted earlier. Form 11 isn't in brand/epfo-forms.json, so the reel says 'joining form' and doesn't name it. The research couldn't open these pages on 18 November 2026 (EPFO's and PIB's sites refused automated reading); the wording above is from search results only, so open each one and confirm it.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job declare_uan_on_joining --by NAME`. Muse never marks a rule checked.
3. **Rule · two_uans** · rule 'two_uans' needs a person to check the source. Find: with more than one UAN, the member tells the employer and emails uanepf@epfindia.gov.in with both UANs; after verification the previous UAN is blocked and the current one kept; the booklet (https://www.epfindia.gov.in/site_docs/PDFs/MiscPDFs/Employees_Information_Booklet.pdf) says to merge older accounts into the latest UAN by filing transfer applications. The research couldn't open these pages on 18 November 2026 (EPFO's and PIB's sites refused automated reading); the wording above is from search results only, so open each one and confirm it.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job two_uans --by NAME`. Muse never marks a rule checked.
4. **Rule · online_claim_kyc** · rule 'online_claim_kyc' needs a person to check the source. Gazette p. 80, para 25(1): the member furnishes 'Aadhaar Number ..., an Aadhaar seeded Bank account number ..., the Permanent account Number ... and the Universal Account Number.' PIB 1 May 2017 (https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=161420): members 'who have activated their UAN and seeded their KYC (Aadhaar) with EPFO will be able to apply for PF final settlement (form19), Pension withdrawal benefit (Form10-C) and PF part withdrawal (Form31)'.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job online_claim_kyc --by NAME`. Muse never marks a rule checked.
5. **Rule · reject_details** · rule 'reject_details' needs a person to check the source. The link reproduces the official reply (it lists mismatches in date of birth, exit date, service details, Aadhaar or bank details). Find the reply on sansad.in, check it says this, and put that official link here instead. The reply is about pension claims; confirm it applies to PF claims too, or say so. (Checked by Divyank Sharma for ep01 on 2026-11-13: same statement and source; confirm it still holds.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job reject_details --by NAME`. Muse never marks a rule checked.
6. **Rule · self_correction** · rule 'self_correction' needs a person to check the source. Quote: 'members whose Universal Account Number (UAN) has already been validated through Aadhaar can update their profile like name, date of birth ... themselves without the requirement of uploading any document. Only, in certain cases where UAN was obtained prior to 1-10-2017, the updation would require certification of employer only.' (Checked by Divyank Sharma for ep01 on 2026-11-13: same statement and source; confirm it still holds.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job self_correction --by NAME`. Muse never marks a rule checked.
7. **Rule · transfer_on_job_change** · rule 'transfer_on_job_change' needs a person to check the source. Form 13 moves the PF from an old employer's account to the new one, so it keeps earning EPF interest; the forms list (brand/epfo-forms.json) has it, checked on 13 November 2026. (Checked by Divyank Sharma for ep04 on 2026-11-14: same statement and source; confirm it still holds.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job transfer_on_job_change --by NAME`. Muse never marks a rule checked.
8. **Rule · exit_date_upload** · rule 'exit_date_upload' needs a person to check the source. Para 24(2)(v): 'Every employer shall, within fifteen days of the close of each month, upload ... details of the employees leaving the service'. For the member's own entry: PIB https://www.pib.gov.in/PressReleasePage.aspx?PRID=1687113 ('record their date of exit themselves'). (Checked by Divyank Sharma for ep01 on 2026-11-13: same statement and source; confirm it still holds.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job exit_date_upload --by NAME`. Muse never marks a rule checked.
9. **Fact · mark_exit_days** · fact 'mark_exit_days' needs a person to check the source. Find: 'After 60 days from the date of leaving of services, the member can him self submit / update Date of Exit online through Member Portal.' The research couldn't open the page (seen in a search snippet only), and the menu (Manage → Mark Exit) may have changed after the July 2026 upgrade: confirm both on the portal. (Checked by Divyank Sharma for ep01 on 2026-11-13: same statement and source; confirm it still holds.)
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job mark_exit_days --by NAME`. Muse never marks a fact checked.
10. **Rule · grievance_epfigms** · rule 'grievance_epfigms' needs a person to check the source. Open it: 'Register Grievance', for PF members, pensioners and employers; the site says 'EPFiGMS is available in UMANG.' (Checked by Divyank Sharma for ep01 on 2026-11-13: same statement and source; confirm it still holds.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job grievance_epfigms --by NAME`. Muse never marks a rule checked.
11. **Rule · services_free** · rule 'services_free' needs a person to check the source. Find: members 'should not pay any fees to third party agents or cyber cafes' for EPFO's services. (Checked by Divyank Sharma for ep01 on 2026-11-13: same statement and source; confirm it still holds.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep06-shivam-new-job services_free --by NAME`. Muse never marks a rule checked.
12. **Script review · version 6b9d83** · The script and hook (version 6b9d83) wait for a person to read and approve them. Nothing else is made until then: no shots or reel.json, photos, screenshots or voice lines.
   - Muse sends the person the script page, https://github.com/aniket007dc/PF_stories/blob/main/episodes/ep06-shivam-new-job/script.md, and waits. The person replies with changes, or writes that the script is OK. Muse makes exactly the changes they ask for and sends them the new page; after their OK, Muse uploads script-approved.json with the version on the page they approved (MUSE.md → N3).

## Still to make

- everything after the script waits for its review: the shots and reel.json (MUSE.md → N4), photos, screenshots, voice lines and the reel

## Passed

- Episode file: brief, data, script, shots and post
- Not a repeat: topic, hook, script and photos are this reel's own (TOPICS.md)

## Posting

Not posted yet. Post only after a person writes "post it", and only if `episodes/ep06-shivam-new-job/posted.json` doesn't exist. Right after posting, upload posted.json (MUSE.md → Step 6).

