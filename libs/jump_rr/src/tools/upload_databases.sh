# Find the latest version of the dataset
ZENODO_ENDPOINT="https://zenodo.org"
DEPOSITION_PREFIX="${ZENODO_ENDPOINT}/api/deposit/depositions"
ORIGINAL_ID="12775236"
DIR_TO_VERSION="$1"

if [ -z "${ORIGINAL_ID}" ]; then # Only get latest id when provided an original one
	echo "Creating new deposition"
	DEPOSITION_ENDPOINT="${DEPOSITION_PREFIX}"
else # Update existing dataset
	echo "Creating new version"
	LATEST_ID=$(curl "${ZENODO_ENDPOINT}/records/${ORIGINAL_ID}/latest" |
		grep records | sed 's/.*href=".*\.org\/records\/\(.*\)".*/\1/')
	DEPOSITION_ENDPOINT="${DEPOSITION_PREFIX}/${LATEST_ID}/actions/newversion"
fi

if [ -z "${ZENODO_TOKEN}" ]; then # Check Zenodo Token
	echo "Access token not available"
	exit 1
else
	echo "Access token found."
fi

# Create new deposition
DEPOSITION=$(curl -H "Content-Type: application/json" \
	-X POST --data "{}" \
	"${DEPOSITION_ENDPOINT}?access_token=${ZENODO_TOKEN}" |
	jq .id)
echo "New deposition ID is ${DEPOSITION}"

# Variables
curl "${DEPOSITION_PREFIX}?access_token=${ZENODO_TOKEN}"
BUCKET_DATA=$(curl "${DEPOSITION_PREFIX}/${DEPOSITION}?access_token=${ZENODO_TOKEN}")
BUCKET=$(echo "${BUCKET_DATA}" | jq --raw-output .links.bucket)

if [ "${BUCKET}" = "null" ]; then
	echo "Could not find URL for upload. Response from server:"
	echo "${BUCKET_DATA}"
	exit 1
fi

# Upload file
echo "Uploading files to bucket ${BUCKET}"
for FILE_TO_VERSION in $(find "${DIR_TO_VERSION}" -name '*.parquet'); do
	echo "${FILE_TO_VERSION}"
	curl --retry 5 \
		--retry-delay 5 \
		-o /dev/null \
		--upload-file ${FILE_TO_VERSION} \
		"${BUCKET}/${FILE_TO_VERSION##*/}?access_token=${ZENODO_TOKEN}"
done

# Upload Metadata
echo -e '{"metadata": {
    "title": "Processed JUMP Datasets: For Web and programmatic exploration.",
    "creators": [
        {
            "name": "Alán F. Muñoz"
        }
    ],
"description":"<p> Step by step tutorial on the <a href=\\"https://broadinstitute.github.io/jump_hub/howto/1_jumprr_steps.html\\">jump hub"</a></p>, and details on the code that produces this tables on our <a href=\\"https://github.com/broadinstitute/monorepo/tree/main/libs/jump_rr#quick-data-access\\">monorepo</a>.",
"upload_type": "dataset",
"access_right": "open"
}}' >metadata.json

NEW_DEPOSITION_ENDPOINT="${DEPOSITION_PREFIX}/${DEPOSITION}"
echo "Uploading file to ${NEW_DEPOSITION_ENDPOINT}"
curl -H "Content-Type: application/json" \
	-X PUT --data @metadata.json \
	"${NEW_DEPOSITION_ENDPOINT}?access_token=${ZENODO_TOKEN}"

# Publish
# echo "Publishing to ${NEW_DEPOSITION_ENDPOINT}"
curl -H "Content-Type: application/json" \
	-X POST --data "{}" \
	"${NEW_DEPOSITION_ENDPOINT}/actions/publish?access_token=${ZENODO_TOKEN}" |
	jq .id
