import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../result/models/analysis_result.dart';

class MealShareService {
  MealShareService._();
  static final MealShareService instance = MealShareService._();

  Future<void> shareMeal({
    required BuildContext context,
    required AnalysisResult result,
    List<String> imagePaths = const [],
  }) async {
    final output = await _buildCard(result: result, imagePaths: imagePaths);
    final box = context.findRenderObject() as RenderBox?;
    await Share.shareXFiles(
      [XFile(output.path, mimeType: 'image/png')],
      text: 'My meal analysis: ${result.overallScore.round()}/100 with Quinone.',
      subject: 'My Quinone meal analysis',
      sharePositionOrigin: box == null
          ? null
          : box.localToGlobal(Offset.zero) & box.size,
    );
  }

  Future<File> _buildCard({
    required AnalysisResult result,
    required List<String> imagePaths,
  }) async {
    const width = 1080.0;
    const height = 1350.0;
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final background = Paint()..color = const Color(0xFFF7F9F7);
    canvas.drawRect(const Rect.fromLTWH(0, 0, width, height), background);

    const primary = Color(0xFF1E6B4C);
    const dark = Color(0xFF173A2B);
    const muted = Color(0xFF63726B);
    const card = Color(0xFFFFFFFF);
    const soft = Color(0xFFE7F2EC);

    _rounded(canvas, const Rect.fromLTWH(42, 42, width - 84, 520), 34, Paint()..color = card);
    final image = await _loadFirstImage(imagePaths);
    if (image != null) {
      _cover(canvas, image, const Rect.fromLTWH(42, 42, width - 84, 390), 34);
      image.dispose();
    } else {
      canvas.drawRRect(
        RRect.fromRectAndRadius(const Rect.fromLTWH(42, 42, width - 84, 390), const Radius.circular(34)),
        Paint()..color = soft,
      );
      _text(canvas, 'MEAL ANALYSIS', const Offset(86, 210), 26, primary, bold: true);
    }
    _text(canvas, _truncate(result.mealName, 42), const Offset(76, 455), 36, dark, bold: true, maxWidth: width - 152);

    _rounded(canvas, const Rect.fromLTWH(42, 590, width - 84, 210), 34, Paint()..color = dark);
    _text(canvas, 'QUINONE', const Offset(78, 628), 24, soft, bold: true);
    _text(canvas, result.overallScore.round().toString(), const Offset(76, 676), 92, Colors.white, bold: true);
    _text(canvas, 'Whole-meal health support score', const Offset(300, 700), 27, const Color(0xFFD9E7DF), maxWidth: 620);

    final scores = result.healthScores.take(4).toList(growable: false);
    for (var i = 0; i < scores.length; i++) {
      final item = scores[i];
      final x = 42.0 + (i % 2) * 516.0;
      final y = 832.0 + (i ~/ 2) * 118.0;
      _rounded(canvas, Rect.fromLTWH(x, y, 492, 96), 24, Paint()..color = card);
      _text(canvas, _truncate(item.label, 24), Offset(x + 24, y + 22), 24, dark, bold: true, maxWidth: 340);
      _text(canvas, '${item.score.round()}', Offset(x + 398, y + 22), 28, primary, bold: true, alignRight: true);
    }

    final scoreRows = math.max(1, (scores.length + 1) ~/ 2);
    final statsY = 832.0 + scoreRows * 118.0 + 24.0;
    _rounded(canvas, Rect.fromLTWH(42, statsY, width - 84, 108), 26, Paint()..color = soft);
    _text(canvas, '${result.calories.round()} kcal', Offset(72, statsY + 26), 28, dark, bold: true);
    _text(canvas, '${result.protein.toStringAsFixed(1)} g protein', Offset(72, statsY + 66), 22, muted);
    _text(canvas, 'Analyse • understand • improve', Offset(width - 72, statsY + 38), 20, primary, bold: true, alignRight: true);

    final picture = recorder.endRecording();
    final rendered = await picture.toImage(width.toInt(), height.toInt());
    final bytes = await rendered.toByteData(format: ui.ImageByteFormat.png);
    rendered.dispose();
    if (bytes == null) throw StateError('Could not create the share image.');
    final directory = await getTemporaryDirectory();
    final file = File('${directory.path}/quinone_share_${DateTime.now().microsecondsSinceEpoch}.png');
    await file.writeAsBytes(bytes.buffer.asUint8List(), flush: true);
    return file;
  }

  Future<ui.Image?> _loadFirstImage(List<String> paths) async {
    for (final path in paths) {
      final file = File(path.trim());
      if (path.trim().isEmpty || !await file.exists()) continue;
      try {
        final bytes = await file.readAsBytes();
        final codec = await ui.instantiateImageCodec(Uint8List.fromList(bytes), targetWidth: 960);
        final frame = await codec.getNextFrame();
        codec.dispose();
        return frame.image;
      } catch (_) {}
    }
    return null;
  }

  void _cover(Canvas canvas, ui.Image image, Rect destination, double radius) {
    final imageRatio = image.width / image.height;
    final targetRatio = destination.width / destination.height;
    var source = Rect.fromLTWH(0, 0, image.width.toDouble(), image.height.toDouble());
    if (imageRatio > targetRatio) {
      final width = image.height * targetRatio;
      source = Rect.fromLTWH((image.width - width) / 2, 0, width, image.height.toDouble());
    } else {
      final height = image.width / targetRatio;
      source = Rect.fromLTWH(0, (image.height - height) / 2, image.width.toDouble(), height);
    }
    canvas.save();
    canvas.clipRRect(RRect.fromRectAndRadius(destination, Radius.circular(radius)));
    canvas.drawImageRect(image, source, destination, Paint());
    canvas.restore();
  }

  void _rounded(Canvas canvas, Rect rect, double radius, Paint paint) {
    canvas.drawRRect(RRect.fromRectAndRadius(rect, Radius.circular(radius)), paint);
  }

  void _text(Canvas canvas, String text, Offset offset, double fontSize, Color color, {bool bold = false, double? maxWidth, bool alignRight = false}) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: fontSize, fontWeight: bold ? FontWeight.w800 : FontWeight.w500, color: color, height: 1.1)),
      maxLines: 2,
      ellipsis: '…',
      textDirection: TextDirection.ltr,
      textAlign: alignRight ? TextAlign.right : TextAlign.left,
    )..layout(maxWidth: maxWidth ?? 900);
    painter.paint(canvas, alignRight ? Offset(offset.dx - painter.width, offset.dy) : offset);
  }

  String _truncate(String value, int max) {
    final clean = value.trim();
    if (clean.length <= max) return clean;
    return '${clean.substring(0, math.max(0, max - 1)).trim()}…';
  }
}
