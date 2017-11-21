# This file is part of the carrier_send_shipments_redyser module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from email import Utils
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not, Equal
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.modules.carrier_send_shipments.tools import unaccent, unspaces
from collections import OrderedDict
from urllib2 import urlopen, URLError
import csv
import cStringIO as StringIO
import datetime
import logging

logger = logging.getLogger(__name__)

__all__ = ['CarrierApi', 'CarrierApiRedyserZip', 'CarrierApiRedyserOffline',
    'CarrierApiRedyserOfflineSendStart', 'CarrierApiRedyserOfflineSend',
    'LoadCarrierApiRedyserZipStart', 'LoadCarrierApiRedyserZip']

REDYSER_LOAD_ZIP = 'http://webservices.redyser.com/services/downloads/canalizaciones_int.csv'


class CarrierApi:
    __metaclass__ = PoolMeta
    __name__ = 'carrier.api'
    redyser_client_code = fields.Char('Redyser Client Code', states={
        'required': Eval('method') == 'redyser',
        'invisible': Eval('method') != 'redyser'
        }, depends=['method'])
    redyser_email = fields.Char('Redyser Email', states={
        'required': Eval('method') == 'redyser',
        'invisible': Eval('method') != 'redyser',
        }, depends=['method'],
        help='Redyser email, separated by comma')
    redyser_email_cc = fields.Char('Redyser CC Email', states={
            'invisible': Eval('method') != 'redyser',
        }, depends=['method'],
        help='Redyser CC email, separated by comma')
    redyser_filename = fields.Char('Redyser Filename', states={
            'required': Eval('method') == 'redyser',
            'invisible': Eval('method') != 'redyser'
        }, depends=['method'],
        help='Prefix Redyser Filename')
    redyser_send_method = fields.Selection([
        ('email', 'Email'),
        ('ftp', 'FTP')], 'Redyser Send Method', required=True)
    redyser_csv_header = fields.Boolean('Redyser CSV Header')

    @staticmethod
    def default_redyser_send_method():
        return 'email'

    @staticmethod
    def default_redyser_csv_header():
        return True

    @classmethod
    def view_attributes(cls):
        return super(CarrierApi, cls).view_attributes() + [
            ('//page[@id="redyser"]', 'states', {
                    'invisible': Not(Equal(Eval('method'), 'redyser')),
                    })]

    @classmethod
    def get_carrier_app(cls):
        '''
        Add Carrier Seur APP
        '''
        res = super(CarrierApi, cls).get_carrier_app()
        res.append(('redyser', 'Redyser'))
        return res

    @staticmethod
    def _get_keys():
        return ['postal_code', 'country_code', 'center_code', 'center_name',
            'service_1030', 'service_saturday', 'max_pickup_time']

    @classmethod
    def test_redyser(cls, api):
        return True


class CarrierApiRedyserZip(ModelSQL, ModelView):
    'Redyser Zip'
    __name__ = 'carrier.api.redyser.zip'
    postal_code = fields.Char('Postal Code', required=True, select=True)
    country_code = fields.Char('Country code')
    center_code = fields.Char('Center code')
    center_name = fields.Char('Center name')
    service_1030 = fields.Boolean('Delivery 10:30')
    service_saturday = fields.Boolean('Delivery Saturdays')
    max_pickup_time = fields.Time('Maximum pickup time')

    def get_rec_name(self, name=None):
        return '%s-%s' % (self.postal_code, self.center_code)

    @classmethod
    def load_redyser_zip(cls):
        '''Upgrade Redyser Zip'''
        zips = cls.search([])
        if zips:
            cls.delete(zips)

        try:
            response = urlopen(REDYSER_LOAD_ZIP)
        except URLError:
            logger.error('Load Zip CSV')
            return

        if not response:
            return

        csv_zips = response.read().decode('iso-8859-1').encode('utf8')
        response.close()

        to_create = []
        for row in csv.reader(csv_zips.splitlines(), delimiter='\t'):
            if not row:
                continue

            new_line = {}
            new_line['postal_code'] = row[0]
            new_line['country_code'] = row[1]
            new_line['center_code'] = row[2]
            new_line['center_name'] = row[3]
            new_line['service_1030'] = True if row[4] == 'S' else False
            new_line['service_saturday'] = True if row[5] == 'S' else False
            if row[6]:
                new_line['max_pickup_time'] = datetime.datetime.strptime(
                    row[6], '%H:%M:%S').time()
            to_create.append(new_line)

        if to_create:
            cls.create(to_create)


class CarrierApiRedyserOffline(ModelSQL, ModelView):
    'Carrier API Redyser Offline'
    __name__ = 'carrier.api.redyser_offline'

    company = fields.Many2One('company.company', 'Company', required=True)
    api = fields.Many2One('carrier.api', 'API', required=True,
        states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state'])
    shipment = fields.Many2One('stock.shipment.out', 'Shipment', required=True,
        domain=[
            ('state', 'in', ['packed', 'done']),
            ],
        states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def get_csv_headers():
        return ['shipment', 'redyser_reference', 'sender_name',
            'sender_address', 'sender_postalcode', 'sender_city',
            'latitude_sender', 'longitude_sender', 'receiver',
            'receiver_address', 'receiver_postalcode', 'receiver_city',
            'latitude_receiver', 'longitude_receiver', 'packages',
            'cashondelivery', 'receiver_phone1', 'receiver_phone2', 'client_code',
            'service_code', 'notes', 'receiver_email', 'sender_email',
            'sender_country', 'receiver_country', 'order_type', 'weight',
            'total_value', 'inssurance_value', 'sender_phone',
            'client_reference', 'packages_ids', 'point_id',
            'destination_contact']

    @classmethod
    def send_redyser_offline(cls):
        API = Pool().get('carrier.api')

        for api in API.search([
                ('method', '=', 'redyser'),
                ]):
            cls.send_redyser_shipments(api)

    @classmethod
    def send_redyser_shipments(cls, api):
        CarrierApi = Pool().get('carrier.api')

        redyser_shipments = cls.search([
            ('api', '=', api),
            ('state', '=', 'draft'),
            ])
        if not redyser_shipments:
            return

        default_service = CarrierApi.get_default_carrier_service(api)

        shipments_data = []
        if api.redyser_csv_header:
            shipments_data.append(cls.create_csv_header())

        for s in redyser_shipments:
            shipment = s.shipment
            if shipment.warehouse.address:
                waddress = shipment.warehouse.address
            else:
                waddress = api.company.party.addresses[0]
            service = shipment.carrier_service or shipment.carrier.service \
                or default_service
            csv_row = cls.create_csv_row(shipment, service, waddress, api)
            shipments_data.append(csv_row)

        # TODO py3.x
        csvfile = StringIO.StringIO()
        csvwriter = csv.writer(csvfile, delimiter='\t')
        for row in shipments_data:
            csvwriter.writerow(row)
        filename = '%s_%s.csv' % (
            api.redyser_filename, datetime.datetime.now().date().isoformat())

        if api.redyser_send_method == 'ftp':
            cls.send_redyser_ftp(api, csvfile, filename)
        else:
            cls.send_redyser_email(api, csvfile, filename)

        cls.write(redyser_shipments, {'state': 'done'})

    @classmethod
    def send_redyser_ftp(cls, api, csvfile, filename):
        # TODO
        cls.raise_user_error('no_allow_ftp')

    @classmethod
    def send_redyser_email(cls, api, csvfile, filename):
        SMTP = Pool().get('smtp.server')

        server = SMTP.get_smtp_server_from_model(cls.__name__)
        if not server:
            cls.raise_user_error('no_smtp_redyser')

        from_ = server.smtp_email
        recipients = api.redyser_email.split(',')
        if api.redyser_email_cc:
            recipients += api.redyser_email_cc.split(',')
        subject = '%s: %s - %s' % (
            api.company.party.name, api.redyser_client_code, filename)

        msg = MIMEMultipart()
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = from_
        msg['To'] = api.redyser_email
        if api.redyser_email_cc:
            msg['Cc'] = api.redyser_email_cc
        msg['Reply-to'] = server.smtp_email
        # msg['Date']     = Utils.formatdate(localtime = 1)
        msg['Message-ID'] = Utils.make_msgid()

        attach = MIMEBase('application', "octet-stream")
        attach.set_payload(csvfile.getvalue())
        attach.add_header('Content-Disposition',
            'attachment; filename="%s"' % filename)
        msg.attach(attach)

        try:
            smtp_server = server.get_smtp_server()
            smtp_server.sendmail(from_, recipients, msg.as_string())
            smtp_server.quit()
            logger.info('Send Redyser Offline: %s' % (filename))
        except:
            cls.raise_user_error('error_smtp')
            logger.error('Send Redyser Offline: %s' % (filename))

    @classmethod
    def create_csv_header(cls):
        row = OrderedDict.fromkeys(cls.get_csv_headers())

        row['shipment'] = 'ALBARAN'
        row['redyser_reference'] = 'REFERENCIA REDYSER'
        row['sender_name'] = 'REMITENTE'
        row['sender_address'] = 'DOMICILIO REMITENTE'
        row['sender_postalcode'] = 'CODIGO POSTAL REMITENTE'
        row['sender_city'] = 'POBLACION REMITENTE'
        row['latitude_sender'] = 'Coordenada longitud remitente'
        row['longitude_sender'] = 'Coordenada latitud remitente'
        row['receiver'] = 'DESTINATARIO'
        row['receiver_address'] = 'DOMICILIO DESTINATARIO'
        row['receiver_postalcode'] = 'CODIGO POSTAL DESTINATARIO'
        row['receiver_city'] = 'POBLACION DESTINATARIO'
        row['latitude_receiver'] = 'Coordenada longitud destinatario'
        row['longitude_receiver'] = 'Coordenada latitud destinatario'
        row['packages'] = 'BULTOS'
        row['cashondelivery'] = 'REEMBOLSO'
        row['receiver_phone1'] = 'TELEFONO1'
        row['receiver_phone2'] = 'TELEFONO2'
        row['client_code'] = 'CLIENTE'
        row['service_code'] = 'Codigo del servicio'
        row['notes'] = 'OBSERVACIONES'
        row['receiver_email'] = 'Mail del destinatario'
        row['sender_email'] = 'Mail del remitente'
        row['receiver_country'] = 'Pais origen'
        row['sender_country'] = 'Pais destino'
        row['order_type'] = 'Tipo de orden'
        row['weight'] = 'Peso'
        row['total_value'] = 'Valor de la mercancia'
        row['inssurance_value'] = 'Valor seguro a todo riesgo'
        row['sender_phone'] = 'TELEFONO3'
        row['client_reference'] = 'REFERENCIA_CLI'
        row['packages_ids'] = 'IDBULTOS'
        row['point_id'] = 'IDPUNTO'
        row['destination_contact'] = 'CONTACTO DESTINO'
        return row.values()

    @classmethod
    def create_csv_row(cls, shipment, service, waddress, api):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        CarrierApi = pool.get('carrier.api')

        sequence, = Sequence.search([('code', '=', 'carrier.api.redyser')],
            limit=1)

        default_service = CarrierApi.get_default_carrier_service(api)
        service = shipment.carrier_service or shipment.carrier.service \
            or default_service

        if api.reference_origin and hasattr(shipment, 'origin'):
            code = shipment.origin and shipment.origin.rec_name or shipment.code
        else:
            code = shipment.code

        row = OrderedDict.fromkeys(cls.get_csv_headers())

        customer = shipment.customer
        delivery_address = shipment.delivery_address
        company = shipment.company
        company_address = company.party.addresses[0]

        row['shipment'] = code
        row['redyser_reference'] = shipment.carrier_tracking_ref
        row['sender_name'] = unaccent(company.party.name)
        row['sender_address'] = unaccent(company_address.street)
        row['sender_postalcode'] = unaccent(company_address.zip)
        row['sender_city'] = unaccent(company_address.city)
        row['latitude_sender'] = None
        row['longitude_sender'] = None
        row['receiver'] = unaccent(customer.name)
        row['receiver_address'] = unaccent(delivery_address.street)
        row['receiver_postalcode'] = unaccent(delivery_address.zip)
        row['receiver_city'] = unaccent(delivery_address.city)
        row['latitude_receiver'] = None
        row['longitude_receiver'] = None
        row['packages'] = shipment.number_packages
        row['cashondelivery'] = shipment.carrier_cashondelivery_price
        row['receiver_phone1'] = unspaces(unaccent(delivery_address.phone
            or customer.phone))
        row['receiver_phone2'] = None
        row['client_code'] = api.redyser_client_code
        row['service_code'] = service.code
        row['notes'] = None
        row['receiver_email'] = unaccent(delivery_address.email
            or customer.email)
        row['sender_email'] = unaccent(company.party.email)
        row['sender_country'] = company_address.country.code
        row['receiver_country'] = delivery_address.country.code
        row['order_type'] = 'E' # recogida o entrega ([R|E])
        row['weight'] = shipment.carrier_weight
        row['total_value'] = shipment.total_amount_func
        row['inssurance_value'] = None
        row['sender_phone'] = unspaces(unaccent(company.party.phone))
        row['client_reference'] = None
        row['packages_ids'] = None
        row['point_id'] = None
        row['destination_contact'] = None
        return row.values()


class CarrierApiRedyserOfflineSendStart(ModelView):
    'Carrier API Seur Offline Send Start'
    __name__ = 'carrier.api.redyser.offline.send.start'
    api = fields.Many2One('carrier.api', 'API', required=True,
        domain=[('method', '=', 'redyser')])


class CarrierApiRedyserOfflineSend(Wizard):
    'Carrier API Seur Offile Send'
    __name__ = 'carrier.api.redyser.offline.send'

    start = StateView('carrier.api.redyser.offline.send.start',
        'carrier_send_shipments_redyser.carrier_send_shipments_redyser_send_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Send', 'send', 'tryton-ok', default=True),
            ])
    send = StateTransition()

    def transition_send(self):
        Offline = Pool().get('carrier.api.redyser_offline')

        api = self.start.api
        Offline.send_redyser_shipments(api)
        return 'end'


class LoadCarrierApiRedyserZipStart(ModelView):
    'Load Carrier API Redyser Zip Start'
    __name__ = 'carrier.api.redyser.zip.load.start'


class LoadCarrierApiRedyserZip(Wizard):
    'Load Carrier API Redyser Zip Start'
    __name__ = 'carrier.api.redyser.zip.load'

    start = StateView('carrier.api.redyser.zip.load.start',
        'carrier_send_shipments_redyser.carrier_api_redyser_load_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Accept', 'accept', 'tryton-ok', default=True),
            ])
    accept = StateTransition()

    def transition_accept(self):
        RedyserZip = Pool().get('carrier.api.redyser.zip')
        RedyserZip.load_redyser_zip()
        return 'end'
