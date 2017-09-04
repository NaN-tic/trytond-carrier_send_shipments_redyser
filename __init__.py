# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import api
from . import shipment


def register():
    Pool.register(
        api.CarrierApi,
        api.CarrierApiRedyserZip,
        api.CarrierApiRedyserOffline,
        api.CarrierApiRedyserOfflineSendStart,
        api.LoadCarrierApiRedyserZipStart,
        shipment.ShipmentOut,
        module='carrier_send_shipments_redyser', type_='model')
    Pool.register(
        api.CarrierApiRedyserOfflineSend,
        api.LoadCarrierApiRedyserZip,
        module='carrier_send_shipments_redyser', type_='wizard')
    Pool.register(
        shipment.RedyserLabel,
        module='carrier_send_shipments_redyser', type_='report')
