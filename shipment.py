# This file is part of the carrier_send_shipments_redyser module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.model import fields
from trytond.modules.jasper_reports.jasper import JasperReport
import tempfile

__all__ = ['ShipmentOut', 'RedyserLabel']


class ShipmentOut:
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.out'

    redyser_channeling = fields.Function(fields.Char('Redyser Channeling'),
        'get_redyser_channeling')
    redyser_barcode = fields.Function(fields.Char('Redyser Barcode'),
        'get_redyser_barcode')
    redyser_current_package = fields.Function(fields.Char('Package'),
        'get_redyser_package')

    def get_redyser_channeling(self, name=None):
        RedyserZip = Pool().get('carrier.api.redyser.zip')

        channeling = RedyserZip.search([
            ('postal_code', '=', self.delivery_address.zip),
            ('country_code', '=', self.delivery_address.country.code)
            ], limit=1)
        if not channeling:
            return
        return ('%s %s') % (
            channeling[0].center_code, channeling[0].center_name)

    def get_redyser_package(self, name=None):
        package = Transaction().context.get('package')
        if package:
            return package
        return 1

    def get_redyser_barcode(self, name=None):
        package = Transaction().context.get('package')
        if package:
            return self._get_barcode(self, package)
        return self._get_barcode(self, 1)

    @classmethod
    def create_label(cls, shipment, api, package=1):
        values = RedyserLabel().execute([shipment.id], {'model': cls.__name__})
        file = cls._generate_file(values)
        return file

    @classmethod
    def _generate_file(cls, values):
        file_data = values[1]
        temp = tempfile.NamedTemporaryFile(prefix='redyser_labels',
            delete=False)
        temp.write(file_data)
        temp.close()
        return temp.name

    @staticmethod
    def _get_barcode(shipment, package):
        """
        CCCCCBBB000000000000Z

        CCCCC Codigo postal destino
        BBB Numero de bulto
        000000000000 Numero de envio del contador reservado en Redyser para
            el cliente. Debe estar incluido en el archivo que recibimos
            con la informacion.
        Z una Z como constante

        """
        Sequence = Pool().get('ir.sequence')

        sequence, = Sequence.search([('code', '=', 'carrier.api.redyser')],
            limit=1)
        counter = (shipment.carrier_tracking_ref if shipment.carrier_tracking_ref
            else Sequence.get_id(sequence.id))
        zip = (shipment.delivery_address.zip if shipment.delivery_address.zip
            else '0')
        barcode = '%s%s%sZ' % (zip.zfill(5), str(package).zfill(3),
            counter.zfill(12))
        return barcode

    @classmethod
    def send_redyser(cls, api, shipments):
        pool = Pool()
        OfflineRedyser = pool.get('carrier.api.redyser_offline')
        Sequence = pool.get('ir.sequence')

        sequence, = Sequence.search([('code', '=', 'carrier.api.redyser')],
            limit=1)

        references = []
        labels = []
        errors = []

        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], {
                'carrier_tracking_ref': Sequence.get_id(sequence.id),
                }))
        if to_write:
            cls.write(*to_write)

        to_create = []
        for shipment in shipments:
            for package in xrange(1, shipment.number_packages + 1):
                with Transaction().set_context(package=package):
                    labels.append(cls.create_label(shipment, api, package))
                references.append(shipment.code)

        to_create.append({
            'api': api,
            'shipment': shipment,
            'state': 'draft'
            })

        if to_create:
            OfflineRedyser.create(to_create)

        return references, labels, errors

    @classmethod
    def print_labels_redyser(cls, api, shipments, reference=None):
        labels = []

        for shipment in shipments:
            for package in xrange(1, shipment.number_packages + 1):
                with Transaction().set_context(package=package):
                    labels.append(cls.create_label(shipment, api, package))

        return labels


class RedyserLabel(JasperReport):
    __name__ = 'carrier.api.redyser.label'

    @classmethod
    def render(cls, report, data, model, ids):
        with Transaction().set_user(0):
            res = super(RedyserLabel, cls).render(report, data, model, ids)
        return res
