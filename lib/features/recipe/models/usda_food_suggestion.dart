class UsdaFoodSuggestion {
  const UsdaFoodSuggestion({
    required this.fdcId,
    required this.description,
    required this.displayName,
    required this.dataType,
    this.foodCategory,
    this.brandOwner,
  });

  final int fdcId;
  final String description;
  final String displayName;
  final String dataType;
  final String? foodCategory;
  final String? brandOwner;

  factory UsdaFoodSuggestion.fromJson(Map<String, dynamic> json) {
    return UsdaFoodSuggestion(
      fdcId: (json['fdc_id'] as num).toInt(),
      description: json['description']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? json['description']?.toString() ?? 'Food',
      dataType: json['data_type']?.toString() ?? 'Unknown',
      foodCategory: json['food_category']?.toString(),
      brandOwner: json['brand_owner']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'fdc_id': fdcId,
        'description': description,
        'display_name': displayName,
        'data_type': dataType,
        if (foodCategory != null) 'food_category': foodCategory,
        if (brandOwner != null) 'brand_owner': brandOwner,
      };
}
