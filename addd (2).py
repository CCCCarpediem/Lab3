from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import tcp
from ryu.lib.packet import arp
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp
from ryu.lib.packet import udp
from ryu.lib.packet import ether_types
from ryu.lib.packet import in_proto


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.check={}
        self.ip_mac={}
        self.flag = 0
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    # send the Rst packet to the host
    # def _send_packet(self,):
    def _send_packet(self, datapath, port, pkt):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt.serialize()
        self.logger.info("packet-out %s" % (pkt,))
        data = pkt.data
        actions = [parser.OFPActionOutput(port=port)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)



    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch

        self.check[format(1, 'd').zfill(16)] = '10:00:00:00:00:01'
        self.check[format(2, 'd').zfill(16)] = '10:00:00:00:00:02'
        self.check[format(3, 'd').zfill(16)] = '10:00:00:00:00:03'
        self.check[format(4, 'd').zfill(16)] = '10:00:00:00:00:04'
        self.ip_mac['10.0.0.1'] = '10:00:00:00:00:01'
        self.ip_mac['10.0.0.2'] = '10:00:00:00:00:02'
        self.ip_mac['10.0.0.3'] = '10:00:00:00:00:03'
        self.ip_mac['10.0.0.4'] = '10:00:00:00:00:04'



        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
  
  
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src

        dpid = format(datapath.id, "d").zfill(16)
        print('datapath_ID is %s',dpid)
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        pk_arp = pkt.get_protocol(arp.arp)
        if pk_arp:
            Arp_reply = packet.Packet()
            Arp_reply.add_protocol(ethernet.ethernet(ethertype=eth.ethertype,
                                               dst=src,
                                               src=self.ip_mac[pk_arp.dst_ip]))
            Arp_reply.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
                                     src_mac=self.ip_mac[pk_arp.dst_ip],
                                     src_ip=pk_arp.dst_ip,
                                     dst_mac=src,
                                     dst_ip=pk_arp.src_ip))
            self._send_packet(datapath, in_port, Arp_reply)


        if not pk_arp:
            ip = pkt.get_protocol(ipv4.ipv4)
            if ip:
                srcip = ip.src
                dstip = ip.dst
                protocol = ip.proto
                # check IP Protocol and create a match for IP
            if eth.ethertype == ether_types.ETH_TYPE_IP:
                # if ICMP Protocol
                if protocol == in_proto.IPPROTO_ICMP:
                    self.flag=1
                    match = parser.OFPMatch(in_port=1,eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip, ipv4_dst=dstip,
                                            ip_proto=protocol,)
                    actions = [parser.OFPActionOutput(2)]
                    if self.check[dpid] == dst:
                        match = parser.OFPMatch(in_port=3, eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip,
                                                ipv4_dst=dstip,
                                                ip_proto=protocol, )
                        actions = [parser.OFPActionOutput(1)]
                    elif self.check[dpid] != dst:
                        match = parser.OFPMatch(in_port=3, eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip,
                                                ipv4_dst=dstip,
                                                ip_proto=protocol, )
                        actions = [parser.OFPActionOutput(2)]


                #  if TCP Protocol
                elif protocol == in_proto.IPPROTO_TCP:
                    self.flag = 1
                    t = pkt.get_protocol(tcp.tcp)
                    # 2,4 can't send http package
                    if (srcip == '10.0.0.2' or srcip == '10.0.0.4')and t.dst_port == 80:
                        mypkt = packet.Packet()
                        mypkt.add_protocol(ethernet.ethernet(ethertype = eth.ethertype,src = dst,dst = src))
                        mypkt.add_protocol(ipv4.ipv4(src = ip.dst,dst = ip.src,proto = 6))
                        mypkt.add_protocol(tcp.tcp(src_port = t.dst_port,dst_port = t.src_port,ack = t.seq + 1,bits = 0b010100,))

                        self._send_packet(datapath,in_port,mypkt)


                    match = parser.OFPMatch(in_port=1,eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip, ipv4_dst=dstip,
                                            ip_proto=protocol, tcp_src=t.src_port, tcp_dst=t.dst_port, )
                    actions = [parser.OFPActionOutput(2)]
                    if self.check[dpid] == dst:
                        match = parser.OFPMatch(in_port=3, eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip,
                                                ipv4_dst=dstip,ip_proto=protocol, tcp_src=t.src_port, tcp_dst=t.dst_port, )
                        actions = [parser.OFPActionOutput(1)]

                    elif self.check[dpid] != dst:
                        match = parser.OFPMatch(in_port=3, eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip,
                                                ipv4_dst=dstip, ip_proto=protocol, tcp_src=t.src_port,tcp_dst=t.dst_port, )
                        actions = [parser.OFPActionOutput(2)]

                #  If UDP Protocol
                elif protocol == in_proto.IPPROTO_UDP:
                    if srcip == '10.0.0.1' or srcip == '10.0.0.4':
                        self.flag = 1
                        match = parser.OFPMatch(in_port=1,eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip, ipv4_dst=dstip,
                                                ip_proto=protocol, udp_src=u.src_port, udp_dst=u.dst_port, )
                        actions = []
                    else:
                        self.flag = 1
                        u = pkt.get_protocol(udp.udp)
                        match = parser.OFPMatch(in_port=1,eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip, ipv4_dst=dstip,
                                                ip_proto=protocol, udp_src=u.src_port, udp_dst=u.dst_port, )
                        actions = [parser.OFPActionOutput(3)]
                        if self.check[dpid] == dst:
                            match = parser.OFPMatch(in_port=2, eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip,
                                                    ipv4_dst=dstip,
                                                    ip_proto=protocol, udp_src=u.src_port, udp_dst=u.dst_port, )
                            actions = [parser.OFPActionOutput(1)]

                        elif self.check[dpid] != dst:
                            match = parser.OFPMatch(in_port=2, eth_type=ether_types.ETH_TYPE_IP, ipv4_src=srcip,
                                                    ipv4_dst=dstip,
                                                   ip_proto=protocol, udp_src=u.src_port, udp_dst=u.dst_port, )
                            actions = [parser.OFPActionOutput(3)]

                if msg.buffer_id != ofproto.OFP_NO_BUFFER and self.flag == 1:
                    self.flag = 0
                    self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                    return
                else:
                    self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
