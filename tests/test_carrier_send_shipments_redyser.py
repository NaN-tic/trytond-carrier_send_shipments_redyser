# This file is part of the carrier_send_shipments_redyser module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.transaction import Transaction


class CarrierSendShipmentsRedyserTestCase(ModuleTestCase):
    'Test Carrier Send Shipments Redyser module'
    module = 'carrier_send_shipments_redyser'

    def setUp(self):
        super(CarrierSendShipmentsRedyserTestCase, self).setUp()
        self.party = POOL.get('party.party')
        self.address = POOL.get('party.address')
        self.shipment_out = POOL.get('stock.shipment.out')

    def test0010redyser_barcode(self):
        'Redyser Barcode'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            party1, = self.party.create([{
                        'name': 'Party 1',
                        }])
            address1, = self.address.create([{
                        'zip': '08720',
                        'party': party1.id,
                        }])
            barcode = self.shipment_out._get_barcode(
                delivery_address=address1, package=1)
            self.assertEqual(barcode, u'08720001000000000001Z')
            transaction.cursor.commit()

def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CarrierSendShipmentsRedyserTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_carrier_send_shipments_redyser.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
