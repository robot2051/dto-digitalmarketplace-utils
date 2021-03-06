import os
import datetime

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

from .s3 import S3ResponseError, get_file_size_up_to_maximum, FILE_SIZE_LIMIT


BAD_SUPPLIER_NAME_CHARACTERS = ['#', '%', '&', '{', '}', '\\', '<', '>', '*', '?', '/', '$',
                                '!', "'", '"', ':', '@', '+', '`', '|', '=', ',', '.']

RESULT_LETTER_FILENAME = 'result-letter.pdf'
AGREEMENT_FILENAME = 'framework-agreement.pdf'
SIGNED_AGREEMENT_PREFIX = 'signed-framework-agreement'
COUNTERSIGNED_AGREEMENT_FILENAME = 'countersigned-framework-agreement.pdf'
SIGNATURE_PAGE_FILENAME = 'signature-page.pdf'


def filter_empty_files(files):
    """Remove any empty files from the list.

    :param files: a dictionary of file attachments
    :return: a dictionary of files with all empty files removed

    """
    return {
        key: contents for key, contents in files.items()
        if file_is_not_empty(contents)
    }


def validate_documents(files):
    """Validate document files for size and format

    :param files: a dictionary of file attachments

    :return: a dictionary of errors, where keys match
             the keys from the ``files`` argument and
             values are validator names used to look
             up the message in the question content
             files. If no errors were found an empty
             dictionary is returned.

    """
    errors = {}
    for field, contents in files.items():
        if not file_is_open_document_format(contents):
            errors[field] = 'file_is_open_document_format'
        elif not file_is_less_than_5mb(contents):
            errors[field] = 'file_is_less_than_5mb'

    return errors


def upload_document(uploader, documents_url, service, field, file_contents, public=True):
    """Upload the document to S3 bucket and return the document URL

    :param uploader: S3 uploader object
    :param documents_url: base assets URL used as root for creating the full
                          document URL.
    :param service: service object used to look up service and supplier code
                    for the generated document name
    :param field: name of the service field that the document URL is saved to,
                  used to generate the document name
    :param file_contents: attached file object
    :param public: if True, set file permission to 'public-read'. Otherwise file
                   is private.

    :return: generated document URL or ``False`` if document upload
             failed

    """
    assert uploader.bucket_short_name in ['documents', 'submissions']

    file_path = generate_file_name(
        service['frameworkSlug'],
        uploader.bucket_short_name,
        service['supplierCode'],
        service['id'],
        field,
        file_contents.filename
    )

    acl = 'public-read' if public else 'private'

    try:
        uploader.save(file_path, file_contents, acl=acl)
    except S3ResponseError:
        return False

    full_url = urlparse.urljoin(
        documents_url,
        file_path
    )

    return full_url


def upload_service_documents(uploader, documents_url, service, request_files, section, public=True):
    assert uploader.bucket_short_name in ['documents', 'submissions']

    files = {field: request_files[field] for field in section.get_question_ids(type="upload")
             if field in request_files}
    files = filter_empty_files(files)
    errors = validate_documents(files)

    if errors:
        return None, errors

    if len(files) == 0:
        return {}, {}

    for field, contents in files.items():
        url = upload_document(
            uploader, documents_url, service, field, contents,
            public=public)

        if not url:
            errors[field] = 'file_can_be_saved'
        else:
            files[field] = url

    return files, errors


def file_is_not_empty(file_contents):
    return not file_is_empty(file_contents)


def file_is_empty(file_contents):
    empty = len(file_contents.read(1)) == 0
    file_contents.seek(0)
    return empty


def file_is_less_than_5mb(file_contents):
    return get_file_size_up_to_maximum(file_contents) < FILE_SIZE_LIMIT


def file_is_open_document_format(file_object):
    return get_extension(file_object.filename) in [
        ".pdf", ".pda", ".odt", ".ods", ".odp"
    ]


def file_is_pdf(file_object):
    """Checks file extension as being PDF."""
    return get_extension(file_object.filename) in [
        ".pdf", ".pda"
    ]


def file_is_csv(file_object):
    """Checks file extension as being CSV."""
    return get_extension(file_object.filename) in [
        ".csv"
    ]


def file_is_zip(file_object):
    """Checks file extension as being ZIP."""
    return get_extension(file_object.filename) in [
        ".zip"
    ]


def file_is_image(file_object):
    """Checks file extension as being JPG. or PNG."""
    return get_extension(file_object.filename) in [
        ".jpg", ".jpeg", ".png"
    ]


def generate_file_name(framework_slug, bucket_short_name, supplier_code, service_id, field, filename, suffix=None):
    if suffix is None:
        suffix = default_file_suffix()

    ID_TO_FILE_NAME_SUFFIX = {
        'serviceDefinitionDocumentURL': 'service-definition-document',
        'termsAndConditionsDocumentURL': 'terms-and-conditions',
        'sfiaRateDocumentURL': 'sfia-rate-card',
        'pricingDocumentURL': 'pricing-document',
    }

    return '{}/{}/{}/{}-{}-{}{}'.format(
        framework_slug,
        bucket_short_name,
        supplier_code,
        service_id,
        ID_TO_FILE_NAME_SUFFIX[field],
        suffix,
        get_extension(filename)
    )


def default_file_suffix():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d-%H%M")


def get_extension(filename):
    file_name, file_extension = os.path.splitext(filename)
    return file_extension.lower()


def get_signed_url(bucket, path, base_url):
    url = bucket.get_signed_url(path)
    if url is not None:
        if base_url is not None:
            url = urlparse.urlparse(url)
            base_url = urlparse.urlparse(base_url)
            url = url._replace(netloc=base_url.netloc, scheme=base_url.scheme).geturl()
        return url


# this method is deprecated
def get_agreement_document_path(framework_slug, supplier_code, document_name):
    return '{0}/agreements/{1}/{1}-{2}'.format(
        framework_slug,
        supplier_code,
        document_name
    )


def get_document_path(framework_slug, supplier_code, bucket_category, document_name):
    return '{0}/{1}/{2}/{2}-{3}'.format(
        framework_slug,
        bucket_category,
        supplier_code,
        document_name
    )


def sanitise_supplier_name(supplier_name):
    """Replace ampersands with 'and' and spaces with a single underscore."""
    sanitised_supplier_name = supplier_name.encode("ascii", errors="ignore").decode("ascii").strip()
    sanitised_supplier_name = sanitised_supplier_name.replace(' ', '_').replace('&', 'and')
    for bad_char in BAD_SUPPLIER_NAME_CHARACTERS:
        sanitised_supplier_name = sanitised_supplier_name.replace(bad_char, '')
    while '__' in sanitised_supplier_name:
        sanitised_supplier_name = sanitised_supplier_name.replace('__', '_')
    return sanitised_supplier_name
