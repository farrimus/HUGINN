#[test_only]
module access_registry::registry_tests {
    use access_registry::registry;
    use sui::test_scenario;

    const OWNER: address = @0xA;
    const TRIBE1: address = @0xB;
    const VETTED1: address = @0xC;
    const STRANGER: address = @0xD;

    #[test]
    fun test_create_registry() {
        let mut scenario = test_scenario::begin(OWNER);
        {
            registry::create(b"keep-7a", test_scenario::ctx(&mut scenario));
        };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            assert!(registry::owner(&reg) == OWNER, 0);
            assert!(std::vector::length(registry::tribe(&reg)) == 0, 1);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    fun test_add_and_check_tribe() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            assert!(registry::is_tribe(&reg, TRIBE1), 0);
            assert!(!registry::is_tribe(&reg, STRANGER), 1);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    fun test_remove_tribe() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            registry::remove_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            assert!(!registry::is_tribe(&reg, TRIBE1), 0);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    #[expected_failure(abort_code = 1)]  // E_NOT_OWNER = 1; use numeric value, not constant path
    fun test_non_owner_cannot_add_tribe() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, STRANGER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    fun test_add_vetted() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_vetted(&mut reg, VETTED1, test_scenario::ctx(&mut scenario));
            assert!(registry::is_vetted(&reg, VETTED1), 0);
            assert!(!registry::is_tribe(&reg, VETTED1), 1);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }
}
