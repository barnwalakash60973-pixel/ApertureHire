"""
Fixed email templates - NO LLM involved, plain string formatting only.
Matches the exact copy specified in the workflow.
"""

from __future__ import annotations

SHORTLIST_EMAIL_SUBJECT = "Your Application Has Been Shortlisted"

SHORTLIST_EMAIL_BODY = """\
Dear {candidate_name},

Thank you for applying for the {job_title} position.

We are pleased to inform you that your resume has been shortlisted for the next stage of our recruitment process.

Our team will share the technical assignment with you shortly.

Thank you for your interest.

Best regards,
HR Team
"""

ASSIGNMENT_EMAIL_SUBJECT = "Technical Assignment - Next Stage"

ASSIGNMENT_EMAIL_BODY = """\
Dear {candidate_name},

Congratulations!

You have successfully qualified for the next stage of our recruitment process.

Assignment:
{assignment_link}

Submission Portal:
{submission_link}

Deadline:
{deadline}

Instructions:
Open the assignment above, work through it, then submit your solution through the Submission Portal link before the deadline.

We wish you the best of luck.

Best regards,
HR Team
"""

REJECTED_EMAIL_SUBJECT = "Update on Your Application"

REJECTED_EMAIL_BODY = """\
Dear {candidate_name},

Thank you for applying for the {job_title} position and for taking the time to share your background with us.

After careful review, we will not be moving forward with your application at this stage. This decision reflects the specific requirements of this role, not the overall strength of your profile.

We encourage you to apply again for future openings that match your experience.

Best regards,
HR Team
"""

REMINDER_EMAIL_SUBJECT = "Reminder: Assignment Submission Due Soon"

REMINDER_EMAIL_BODY = """\
Dear {name},

This is a reminder that your technical assignment for {campaign_name} is due soon.

Deadline: {deadline}

Please submit through the link sent in your original assignment email before the deadline.

Best regards,
HR Team
"""

OVERDUE_EMAIL_SUBJECT = "Assignment Deadline Passed"

OVERDUE_EMAIL_BODY = """\
Dear {name},

The submission deadline for your technical assignment for {campaign_name} has passed and we have not received your submission.

If you believe this is an error or need an extension, please reach out to us directly.

Best regards,
HR Team
"""

FINAL_SELECTED_EMAIL_SUBJECT = "Congratulations - You Have Been Selected"

FINAL_SELECTED_EMAIL_BODY = """\
Dear {candidate_name},

Congratulations! Based on your assignment evaluation, you have been selected for the {job_title} position.

Our team will reach out shortly with next steps.

Best regards,
HR Team
"""

FINAL_REJECTED_EMAIL_SUBJECT = "Update on Your Application"

FINAL_REJECTED_EMAIL_BODY = """\
Dear {candidate_name},

Thank you for completing the technical assignment for the {job_title} position.

After careful evaluation, we will not be moving forward with your application at this stage.

We appreciate the time and effort you put into your submission and encourage you to apply again in the future.

Best regards,
HR Team
"""

OTP_EMAIL_SUBJECT = "Your Password Reset Code"

OTP_EMAIL_BODY = """\
Hi {name},

Your one-time password reset code is:

{otp}

This code expires in {expire_minutes} minutes. If you didn't request a password reset, you can safely ignore this email.

Best regards,
AI Recruitment Assistant
"""
