LABELS = {
    "likely_ai": "AI-generated content suspected. Multiple automated signals suggest AI involvement, but this assessment is not proof of authorship. The creator may request a review.",
    "likely_human": "Likely human-written. Automated signals are consistent with human authorship, but this assessment cannot verify who created the content.",
    "uncertain": "Authorship uncertain. The available signals do not support a reliable AI-versus-human assessment. No definitive attribution is made.",
}


def label_for(attribution):
    return LABELS[attribution]

