"""
Message Generator — Creates personalized WhatsApp messages per risk tier.
Uses AI (Groq/Llama) for Critical patients, templates for others.
"""

from integrations.llama_service import generate_ai_response


def generate_message(patient, risk):
    """Return a personalized WhatsApp reminder message."""
    name = patient.get('name', 'Patient')
    age = patient.get('age', '')
    disease = patient.get('disease', '')
    test = patient.get('last_test', patient.get('test_required', 'routine check'))
    result = patient.get('last_result', 'N/A')

    if risk == 'Critical':
        return _ai_message(name, age, disease, test, result)
    elif risk == 'High':
        return _high_risk_template(name, age, disease, test, result)
    elif risk == 'Medium':
        return _medium_risk_template(name, age, disease, test, result)
    else:
        return _low_risk_template(name, disease, test)


def _ai_message(name, age, disease, test, result):
    """Use AI to craft a highly personalized critical-risk message."""
    prompt = f"""You are a healthcare outreach assistant. Write a short, empathetic WhatsApp reminder message (max 200 words) for a patient:

Name: {name}
Age: {age}
Disease: {disease}
Last test: {test}
Last result: {result}

The patient is at CRITICAL risk. Persuade them to schedule a test immediately.
Mention specific health complications they could face.
Offer home sample collection as a convenience option.
End with a clear call-to-action: reply YES to schedule.
Keep the tone warm but urgent. Use emojis sparingly."""

    return generate_ai_response(prompt)


def _high_risk_template(name, age, disease, test, result):
    return (
        f"Hi {name} 👋\n\n"
        f"Your last {test} result was {result}, which indicates your {disease} may not be well controlled.\n\n"
        f"At age {age}, uncontrolled {disease} can increase the risk of complications such as "
        f"kidney damage, nerve problems, and heart disease.\n\n"
        f"A quick {test} test helps doctors detect problems early and adjust treatment if needed.\n\n"
        f"We can arrange a convenient home sample collection for you.\n\n"
        f"Reply YES to schedule your test this week."
    )


def _medium_risk_template(name, age, disease, test, result):
    return (
        f"Hi {name} 👋\n\n"
        f"Your previous {test} result was {result}. Regular monitoring helps keep your {disease} under control.\n\n"
        f"Since you are {age}, staying proactive with health checks is important.\n\n"
        f"We can arrange a home sample collection at your convenience.\n\n"
        f"Reply YES to book a slot."
    )


def _low_risk_template(name, disease, test):
    return (
        f"Hi {name} 👋\n\n"
        f"It's time for your routine {test} check to keep your {disease} monitored.\n\n"
        f"Regular testing helps prevent future complications.\n\n"
        f"Reply YES if you'd like us to arrange a home sample collection."
    )
