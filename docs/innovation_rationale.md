# Innovation Feature: Candidate Feedback Composer

## The problem
HireLucent helps an interviewer screen CVs, interview candidates and write an evidence-based assessment. But once the decision is made, the candidate usually hears nothing, or receives a generic "we went with other candidates" email. Most applicants are rejected at screening and never learn why. Writing an honest, respectful answer for every candidate takes time, and doing it by hand is risky: a rushed message can mention something unfair, unrelated to the job or not true for that person.

## What the feature does
After the interviewer decides, the Candidate Feedback Composer prepares the candidate's email. For candidates rejected after screening or after the interview, the AI writes personal feedback from that candidate's own saved evidence, their requirement results or their approved report, naming real strengths and the job-related areas to grow in, worded for the role's level. Hired candidates and candidates whose CV could not be read get a fixed, polite message. Every draft passes a fairness check: code rules block scores, other candidates, personal topics, promises and points that are not backed by evidence, and an AI tone review checks that the email is respectful. The interviewer then reviews, edits or asks for changes; nothing is sent without their approval. Emails can be sent one by one or all at once, and each sent email is recorded.

## Who benefits
- **Candidates** get a timely, specific and respectful answer they can learn from.
- **Interviewers** save time, especially for the many candidates rejected at screening, while staying in control.
- **The company** treats every applicant consistently and protects its reputation as an employer.

## Value added
It completes the hiring flow: the platform already explains its decisions to the interviewer, and now that explanation reaches the candidate in a fair form. It reuses the evidence HireLucent already collects, so the feedback is traceable rather than invented, and it keeps the platform's core principle: AI assists, people decide.

## Why I chose it over the alternatives
- **Inclusive JD Checker** (flags biased wording in job descriptions): useful, but close to the existing JD creation step, so less original.
- **Live Coverage Nudges** (reminds the interviewer of unexplored requirements during the call): too close to F5 requirement coverage and F10 interview quality, and risky with live AI calls on a free tier.
- **Talent Pool Rediscovery** (matches past candidates to new jobs): reusing CVs across jobs would need new consent and retention rules.

The Feedback Composer was original, clearly relevant, safe for privacy, and buildable on what HireLucent already has.

## Scope
To keep the scope tight, decisions are Hire or Reject only, sending starts from buttons (a chatbot path is future work), and offer details such as salary or start dates stay out, because offers are outside the BID.
