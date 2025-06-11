# Parse Pubchem Compounds' XML and produce a csv with columns pubchem_id, fingerprint and inchikey.
BEGIN{
    print("pubchem_id","fingerprint","inchikey")
}
{
    # ID
    if ($0 ~ /PC-CompoundType_id_cid/){
	arr[0] = $3
    }

    # Fingerprint
    if ($0 ~ /InfoData_value_binary/){
	arr[1] = $3
    }

    # InChiKey
    if ($0 ~ /PC-Urn_label>InChIKey/){
	new_compound=1
    }
    
    if (($0 ~ /PC-InfoData_value_sval>/) && (new_compound==1)){
	arr[2] = $3
	print(arr[0],arr[1],arr[2])

	# Clean up
	new_compound=0
	delete arr
    }
}
