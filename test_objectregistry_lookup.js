/**
 * Test script for ObjectRegistry-based StorageUnit lookup
 * Run in browser console at https://135.181.95.84:8745/static/structure.html?itemId=1000000018848&tenant=utopia
 */

async function testObjectRegistryLookup() {
  const itemId = new URLSearchParams(window.location.search).get('itemId');
  const tenant = new URLSearchParams(window.location.search).get('tenant');

  console.log('=== Testing ObjectRegistry Lookup ===');
  console.log('itemId:', itemId);
  console.log('tenant:', tenant);

  // Step 1: Get ObjectRegistry singleton
  console.log('\n[STEP 1] Fetching ObjectRegistry singleton...');
  const registryQuery = {
    query: `query GetObjectRegistry($type: String!) {
      objects(filter: {type: $type}, first: 1) {
        nodes {
          address
        }
      }
    }`,
    variables: {
      type: "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75::object_registry::ObjectRegistry"
    }
  };

  try {
    const resp1 = await fetch('https://graphql.testnet.sui.io/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(registryQuery)
    });
    const registryResponse = await resp1.json();
    console.log('Registry response:', registryResponse);

    if (registryResponse?.errors?.length > 0) {
      throw new Error('GraphQL error: ' + registryResponse.errors[0]?.message);
    }

    const registryObjectId = registryResponse?.data?.objects?.nodes?.[0]?.address;
    console.log('✅ Found ObjectRegistry:', registryObjectId);

    // Step 2: Query ObjectRegistry contents to find StorageUnit by itemId
    console.log('\n[STEP 2] Querying ObjectRegistry for itemId:', itemId);
    const lookupQuery = {
      query: `query GetRegistryEntry($id: SuiAddress!) {
        object(address: $id) {
          asMoveObject {
            contents {
              json
            }
          }
        }
      }`,
      variables: { id: registryObjectId }
    };

    const resp2 = await fetch('https://graphql.testnet.sui.io/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lookupQuery)
    });
    const lookupResponse = await resp2.json();
    console.log('Registry contents:', lookupResponse);

    if (lookupResponse?.errors?.length > 0) {
      throw new Error('GraphQL error: ' + lookupResponse.errors[0]?.message);
    }

    const registryJson = lookupResponse?.data?.object?.asMoveObject?.contents?.json;
    console.log('Registry JSON structure:', Object.keys(registryJson || {}));

    // Find matching entry
    let storageUnitObjectId = null;
    if (registryJson?.items && Array.isArray(registryJson.items)) {
      console.log('Found items array, searching for itemId:', itemId);
      for (const item of registryJson.items) {
        console.log('  Checking item:', item);
        if (item.key?.item_id === itemId && item.key?.tenant === tenant) {
          storageUnitObjectId = item.value;
          console.log('✅ Found StorageUnit ID:', storageUnitObjectId);
          break;
        }
      }
    }

    if (!storageUnitObjectId) {
      throw new Error(`itemId "${itemId}" not found in ObjectRegistry`);
    }

    // Step 3: Query the StorageUnit to get assembly_id
    console.log('\n[STEP 3] Fetching StorageUnit metadata...');
    const ssuQuery = {
      query: `query GetFullObject($id: SuiAddress!) {
        object(address: $id) {
          asMoveObject {
            contents {
              json
            }
          }
        }
      }`,
      variables: { id: storageUnitObjectId }
    };

    const resp3 = await fetch('https://graphql.testnet.sui.io/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ssuQuery)
    });
    const ssuResponse = await resp3.json();
    console.log('StorageUnit response:', ssuResponse);

    if (ssuResponse?.errors?.length > 0) {
      throw new Error('GraphQL error: ' + ssuResponse.errors[0]?.message);
    }

    const storageUnitData = ssuResponse?.data?.object?.asMoveObject?.contents?.json;
    console.log('StorageUnit JSON keys:', Object.keys(storageUnitData || {}));
    console.log('StorageUnit data:', storageUnitData);

    // Find assembly_id
    const assemblyId = storageUnitData?.metadata?.assembly_id ||
                       storageUnitData?.assembly_id ||
                       storageUnitData?.assemblyId;

    console.log('\n✅ SUCCESS! assembly_id:', assemblyId);
    return assemblyId;

  } catch (e) {
    console.error('❌ Error:', e.message);
    console.error(e);
  }
}

// Run the test
testObjectRegistryLookup();
